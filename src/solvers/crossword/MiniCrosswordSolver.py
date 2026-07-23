"""
NYT Mini crossword solver -- a deliberate LLM + deterministic-search hybrid.

A crossword couples two subproblems: answering natural-language clues (semantic,
no clean algorithm -> LLM) and filling the grid so every across/down entry is a
real word and all crossings agree (a constraint-satisfaction problem -> exact
algorithm). Per design principle #2 we keep the algorithmic half algorithmic:

  1. The LLM answers every clue in ONE batched call, returning a few candidate
     answers per slot at the exact required length.
  2. A deterministic backtracking CSP fills the grid from those candidates plus a
     human wordlist, enforcing crossing-letter agreement. A wrong clue answer is
     therefore corrected by its crossings instead of poisoning the grid.
  3. Any slot the CSP still cannot fill is re-queried once, now with the crossing
     letters already known (e.g. "_A_DY"), then the CSP runs again.

We solve from clues, never from the answer key: the scraped ``answers`` grid is
used only to score the result. Only the Mini is freely fetchable; the full-size
Daily and Sunday crosswords are gated behind a NYT subscription and are out of
scope for the free daily run.
"""
from datetime import datetime, timedelta
from time import time
from typing import Dict, List, Optional, Tuple

import os

from solvers.BaseSolver import BaseSolver
from solvers.scraping import fetch_json
from solvers import llm

LISTING_URL = "https://www.nytimes.com/svc/crosswords/v3/puzzles.json"
CONTENT_URL = "https://www.nytimes.com/svc/crosswords/v2/puzzle"
WORDS_FILE_PATH = "wordlist.txt"
MAX_CANDIDATES_PER_SLOT = 6
MAX_ROUNDS = 5  # solve/revise iterations before giving up on convergence

SYSTEM_PROMPT = (
    "You are an expert American (NYT-style) crossword solver. Apply these conventions:\n"
    "- The answer never just repeats a key word from its clue: 'Where wedding rings "
    "are exchanged' is ALTAR, not RINGS.\n"
    "- Clue and answer share part of speech, tense, and number: a plural clue takes a "
    "plural answer (usually +S); a past-tense clue takes a past-tense answer (usually "
    "+ED/+D); an '-ing' clue takes an '-ing' answer.\n"
    "- A clue ending in '?' is a pun or wordplay, so the answer is figurative, not "
    "literal.\n"
    "- Abbreviation cues ('Abbr.', 'for short', 'briefly', 'in brief', or an "
    "abbreviation/symbol/acronym in the clue) mean the answer is itself abbreviated.\n"
    "- A foreign word or place in the clue ('in Paris', 'Spanish for ...') means the "
    "answer is in that language.\n"
    "- Fill-in-the-blank and '___' clues are completed literally, often with a common "
    "phrase, name, or brand.\n"
    "- Casual, slang, or pop-culture clues take slang or proper-noun answers "
    "(e.g. NEATO, JCREW, OKED); do not shy away from names and brands.\n"
    "- Short 3-4 letter slots are frequently recurring crossword fill. When the known "
    "letters fit, strongly consider common answers such as OREO, ORE, ERA, AREA, IDEA, "
    "ALOE, ARIA, OBOE, EPEE, ETUI, ANTE, ACRE, ISLE, OLEO, ODE, ESE, ETA, ELI, ENO, "
    "ONO, ASEA, ALEE, EKE, EEL, OAR, AAH, AHA, ELIE, ERIE, ESAU, ARLO.\n"
    "- Every answer must be a REAL word, name, phrase, or abbreviation -- never invent "
    "letters just to fit a length or crossing.\n"
    "Answers are single entries with NO spaces or punctuation, ALL CAPS, and EXACTLY "
    "the stated number of letters. Respond ONLY with JSON."
)


class Slot:
    """One across or down entry: its cells (grid indices), clue, and length."""
    def __init__(self, slot_id: str, cells: List[int], clue: str) -> None:
        self.id = slot_id
        self.cells = cells
        self.clue = clue
        self.length = len(cells)


def build_slots(width: int, clues: Dict[str, list]) -> List[Slot]:
    """Turn the NYT clue lists into across/down slots with their cell indices.
    Across cells step by 1, down cells step by the grid width."""
    slots = []
    for direction, step in (("A", 1), ("D", width)):
        for clue in clues.get(direction, []):
            cells = list(range(clue["clueStart"], clue["clueEnd"] + 1, step))
            slots.append(Slot(f"{direction}{clue['clueNum']}", cells, clue["value"]))
    return slots


def _consistent(word: str, slot: Slot, grid: Dict[int, str]) -> bool:
    return all(grid.get(cell) is None or grid.get(cell) == word[i]
               for i, cell in enumerate(slot.cells))


def fill_grid(slots: List[Slot], candidates: Dict[str, List[str]],
              base_grid: Optional[Dict[int, str]] = None) -> Optional[Dict[int, str]]:
    """Backtracking search for a complete grid where every slot holds one of its
    candidate words and all crossings agree. Starts from ``base_grid`` (letters
    already locked in by other slots) and only assigns ``slots``. Returns the
    filled grid (cell->letter) or None if no full assignment exists. Slots are
    ordered most-constrained-first (MRV) at each step for speed."""
    grid: Dict[int, str] = dict(base_grid) if base_grid else {}
    assigned: Dict[str, str] = {}

    def backtrack() -> bool:
        if len(assigned) == len(slots):
            return True
        # MRV: the unassigned slot with the fewest currently-consistent candidates
        best, best_options = None, None
        for slot in slots:
            if slot.id in assigned:
                continue
            options = [w for w in candidates.get(slot.id, []) if _consistent(w, slot, grid)]
            if best_options is None or len(options) < len(best_options):
                best, best_options = slot, options
                if not options:
                    break  # dead end: prune immediately
        if best is None or not best_options:
            return False
        for word in best_options:
            placed = [cell for cell in best.cells if grid.get(cell) is None]
            for i, cell in enumerate(best.cells):
                grid[cell] = word[i]
            assigned[best.id] = word
            if backtrack():
                return True
            del assigned[best.id]
            for cell in placed:
                grid.pop(cell, None)
        return False

    return grid if backtrack() else None


def greedy_partial(slots: List[Slot], candidates: Dict[str, List[str]],
                   base_grid: Optional[Dict[int, str]] = None) -> Dict[int, str]:
    """Best-effort fill when no complete solution exists: assign slots
    most-constrained-first, skipping any with no consistent candidate. Leaves the
    unresolved cells blank so scoring still credits the letters we did get."""
    grid: Dict[int, str] = dict(base_grid) if base_grid else {}
    remaining = list(slots)
    while remaining:
        remaining.sort(key=lambda s: len([w for w in candidates.get(s.id, []) if _consistent(w, s, grid)]))
        slot = remaining.pop(0)
        for word in candidates.get(slot.id, []):
            if _consistent(word, slot, grid):
                for i, cell in enumerate(slot.cells):
                    grid[cell] = word[i]
                break
    return grid


def fill_grid_prefer_llm(slots: List[Slot], llm_cands: Dict[str, List[str]],
                         dictionary: Dict[int, List[str]]) -> Dict[int, str]:
    """Fill the grid while trusting the model's answers. A single clue the model
    can't answer must not force a *correct* crossing answer to be overwritten just
    to complete the grid, so:

      1. Best case: a complete grid using the LLM answers alone.
      2. Otherwise lock a mutually-consistent set of LLM answers (most-confident
         slots first), then fill only the leftover slots from the dictionary,
         constrained by the locked letters -- the locked answers are never changed.

    Returns a grid that may leave a few cells blank if nothing fits."""
    llm_only = {s.id: llm_cands.get(s.id, []) for s in slots}
    full = fill_grid(slots, llm_only)
    if full is not None:
        return full

    grid: Dict[int, str] = {}
    locked = set()
    for slot in sorted(slots, key=lambda s: 0 if llm_cands.get(s.id) else 1):
        for word in llm_cands.get(slot.id, []):
            if _consistent(word, slot, grid):
                for i, cell in enumerate(slot.cells):
                    grid[cell] = word[i]
                locked.add(slot.id)
                break

    remaining = [s for s in slots if s.id not in locked]
    if not remaining:
        return grid
    cand = {s.id: llm_cands.get(s.id, []) + dictionary.get(s.length, []) for s in remaining}
    filled = fill_grid(remaining, cand, base_grid=grid)
    return filled if filled is not None else greedy_partial(remaining, cand, base_grid=grid)


class MiniCrosswordSolver(BaseSolver):
    OUTPUT_DIRECTORY_PATH = "solutions/crossword"

    def __init__(self, ds: str = None) -> None:
        super().__init__(ds)
        self.width = 0
        self.height = 0
        self.layout: List[int] = []
        self.answers: List[Optional[str]] = []
        self.slots: List[Slot] = []
        self.grid: Dict[int, str] = {}
        self.llm_answers: Dict[str, List[str]] = {}
        self.solved = False
        self.cells_correct = 0
        self.cells_total = 0
        self.scrape_puzzle()

    def scrape_puzzle(self) -> None:
        print("Fetching puzzle from NYT website...")
        listing = fetch_json(f"{LISTING_URL}?publish_type=mini&date_start={self.ds}&date_end={self.ds}")
        results = listing.get("results") or []
        if not results:
            raise ValueError(f"No Mini crossword listed for {self.ds}")
        self.puzzle_id = results[0]["puzzle_id"]

        content = fetch_json(f"{CONTENT_URL}/{self.puzzle_id}.json")["results"][0]
        meta = content["puzzle_meta"]
        self.width, self.height = meta["width"], meta["height"]
        data = content["puzzle_data"]
        self.layout = data["layout"]
        self.answers = [a.upper() if a else None for a in data["answers"]]
        self.slots = build_slots(self.width, data["clues"])
        print("Fetching puzzle from NYT website... done!")

    def load_dictionary(self, lengths: set) -> Dict[int, List[str]]:
        """Human wordlist grouped by the slot lengths we need. Used only to help
        crossings resolve; the answer grid is never consulted while solving."""
        by_len: Dict[int, List[str]] = {n: [] for n in lengths}
        path = os.path.join("./", WORDS_FILE_PATH)
        if not os.path.exists(path):
            return by_len
        with open(path) as f:
            for line in f:
                word = line.strip().upper()
                if word.isalpha() and len(word) in by_len:
                    by_len[len(word)].append(word)
        return by_len

    def _crossings_lines(self) -> List[str]:
        """Human-readable list of every shared cell, so the model can make its
        answers interlock instead of solving each clue in isolation."""
        cell_members: Dict[int, list] = {}
        for slot in self.slots:
            for pos, cell in enumerate(slot.cells):
                cell_members.setdefault(cell, []).append((slot.id, pos))
        lines = []
        for cell in sorted(cell_members):
            across = [m for m in cell_members[cell] if m[0].startswith("A")]
            down = [m for m in cell_members[cell] if m[0].startswith("D")]
            for a_id, a_pos in across:
                for d_id, d_pos in down:
                    lines.append(f"  {a_id} letter {a_pos + 1} = {d_id} letter {d_pos + 1}")
        return lines

    def _ask_clues(self, patterns: Optional[Dict[str, str]] = None,
                   invalid: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """One batched LLM call for candidate answers to EVERY slot. On revision
        rounds ``patterns`` holds each slot's current letters (from where the
        Across/Down answers already agree) and ``invalid`` names entries that
        currently spell non-words; the model is shown the grid so far and asked to
        fix those, which is the feedback loop that lets it iterate to a real fill."""
        by_id = {s.id: s for s in self.slots}
        lines = [
            "Solve this NYT Mini crossword. Every Across and Down answer must "
            "interlock, so shared cells hold the SAME letter -- solve the whole grid "
            "together, not each clue alone.",
            "Answers may be phrases (write with NO spaces), proper nouns, or "
            "abbreviations; prefer the common crossword answer. Give several "
            "candidates per clue when unsure so the crossings can decide.",
            "",
        ]
        if patterns:  # revision round: show the current grid and the locked letters
            lines.append("Grid so far ('.' = still empty). Some answers are wrong; "
                         "revise them so EVERY across and down entry is a real word or "
                         "name and all crossings still agree:")
            lines.append("")
            lines.extend(self.grid_rows())
            lines.append("")
            if invalid:
                lines.append("These entries currently spell NON-words (a wrong crossing "
                             "forced them) -- they are the priority to fix:")
                for item in invalid:
                    lines.append(f"  {item}")
                lines.append("")
        for direction, label in (("A", "Across"), ("D", "Down")):
            entries = [s.id for s in self.slots if s.id.startswith(direction)]
            lines.append(f"{label}:")
            for sid in entries:
                slot = by_id[sid]
                hint = f" [{patterns[sid]}]" if patterns else ""
                lines.append(f"  {sid} ({slot.length}){hint}: {slot.clue}")
            lines.append("")
        lines.append("Crossings (these letters must match):")
        lines.extend(self._crossings_lines())
        lines.append("")
        lines.append('Respond as JSON mapping each id to up to '
                     f'{MAX_CANDIDATES_PER_SLOT} uppercase answers (best first), '
                     'each EXACTLY the stated length and consistent with the '
                     'crossings, e.g. {"A1": ["HEN"], "D2": ["EDDY"]}.')
        response = llm.complete_json("\n".join(lines), system=SYSTEM_PROMPT, max_tokens=3000)

        out: Dict[str, List[str]] = {}
        for sid, words in (response or {}).items():
            if sid not in by_id:
                continue
            length = by_id[sid].length
            clean = []
            for word in words if isinstance(words, list) else [words]:
                w = "".join(ch for ch in str(word).upper() if ch.isalpha())
                if len(w) == length and w not in clean:
                    clean.append(w)
            out[sid] = clean[:MAX_CANDIDATES_PER_SLOT]
        return out

    def _pattern(self, slot: Slot) -> str:
        return "".join(self.grid.get(cell, "_") for cell in slot.cells)

    def play(self) -> None:
        """Iteratively solve: get answers, fill the grid, feed the resulting
        crossing letters back to the model to revise, and repeat until the grid
        stops changing (or a round budget is hit). This gives the model the
        feedback loop it lacks in a single shot -- a clue it got wrong blind often
        becomes obvious once a crossing reveals a letter or two."""
        dictionary = self.load_dictionary({s.length for s in self.slots})
        candidates: Dict[str, List[str]] = {}
        self.grid = {}
        previous_signature = None
        invalid: Optional[List[str]] = None

        for round_index in range(MAX_ROUNDS):
            patterns = None if round_index == 0 else {s.id: self._pattern(s) for s in self.slots}
            fresh = self._ask_clues(patterns, invalid)
            for sid, words in fresh.items():  # newest answers first so revisions win
                candidates[sid] = words + [w for w in candidates.get(sid, []) if w not in words]
            self.grid = fill_grid_prefer_llm(self.slots, candidates, dictionary)

            signature = tuple(sorted(self.grid.items()))
            if signature == previous_signature:
                break  # a round changed nothing -> converged
            previous_signature = signature
            invalid = self._invalid_entries(candidates, dictionary)

        self.llm_answers = candidates
        self._score()

    def _invalid_entries(self, candidates: Dict[str, List[str]],
                         dictionary: Dict[int, List[str]]) -> List[str]:
        """Slots whose current filled entry is a non-word: fully placed, yet not a
        word the model proposed for it nor in the human wordlist. These are the
        letter-collisions a wrong crossing produced (e.g. 'BWSL'), so they make the
        best fix targets for the next revision round."""
        out = []
        for slot in self.slots:
            entry = self._pattern(slot)
            if "_" in entry:
                continue
            if entry in candidates.get(slot.id, []):
                continue
            if entry in set(dictionary.get(slot.length, [])):
                continue
            out.append(f"{slot.id} = {entry}")
        return out

    def _entry(self, slot: Slot, source: Dict[int, str]) -> str:
        return "".join(source.get(cell, "_") for cell in slot.cells)

    def _answer(self, slot: Slot) -> str:
        return "".join(self.answers[cell] or "_" for cell in slot.cells)

    def slot_report(self) -> List[str]:
        """Per-slot breakdown for the logs: what we filled vs the real answer, and
        whether the model's top candidate was right. Uses the answer key only to
        report, never to solve."""
        answers_by_cell = {i: a for i, a in enumerate(self.answers)}
        rows = []
        for slot in self.slots:
            filled = self._entry(slot, self.grid)
            actual = self._entry(slot, answers_by_cell)
            top = (self.llm_answers.get(slot.id) or ["-"])[0]
            mark = "OK " if filled == actual else "X  "
            rows.append(f"  {mark}{slot.id} {filled:<7} (answer {actual}, llm {top}): {slot.clue}")
        return rows

    def _score(self) -> None:
        white = [i for i, cell in enumerate(self.layout) if cell == 1]
        self.cells_total = len(white)
        self.cells_correct = sum(1 for i in white if self.grid.get(i) == self.answers[i])
        self.solved = self.cells_correct == self.cells_total and self.cells_total > 0

    def grid_rows(self) -> List[str]:
        rows = []
        for r in range(self.height):
            row = []
            for c in range(self.width):
                i = r * self.width + c
                row.append("#" if self.layout[i] == 0 else self.grid.get(i, "."))
            rows.append(" ".join(row))
        return rows

    def solve(self) -> None:
        date = datetime.strptime(self.ds, "%Y-%m-%d")
        print(f"Solving the Mini crossword for {date.strftime('%B %d, %Y')}:\n")

        start = time()
        try:
            self.play()
        except llm.LLMError as e:
            print(f"LLM unavailable, recording unsolved: {e}")
            self._score()
        end = time()

        print("\n".join(self.grid_rows()))
        print()
        print("\n".join(self.slot_report()))
        pct = (self.cells_correct / self.cells_total * 100) if self.cells_total else 0
        print(f"\n{'Solved' if self.solved else 'Filled'} "
              f"{self.cells_correct}/{self.cells_total} cells ({pct:.0f}%).")

        self.write_solved_puzzle(start, end)

    def write_solved_puzzle(self, start: float, end: float) -> None:
        data = {
            "puzzle_id": self.puzzle_id,
            "ds": self.ds,
            "width": self.width,
            "height": self.height,
            "solved": self.solved,
            "cells_correct": self.cells_correct,
            "cells_total": self.cells_total,
            "grid": self.grid_rows(),
            "llm_answers": {sid: words for sid, words in self.llm_answers.items() if words},
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_solution(data)
