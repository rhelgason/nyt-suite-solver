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

SYSTEM_PROMPT = (
    "You are an expert crossword solver. Answers are single entries with NO spaces "
    "or punctuation, all uppercase, and EXACTLY the stated number of letters. "
    "Respond ONLY with JSON."
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


def fill_grid(slots: List[Slot], candidates: Dict[str, List[str]]) -> Optional[Dict[int, str]]:
    """Backtracking search for a complete grid where every slot holds one of its
    candidate words and all crossings agree. Returns the filled grid (cell->letter)
    or None if no full assignment exists. Slots are ordered most-constrained-first
    (MRV) at each step for speed."""
    grid: Dict[int, str] = {}
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


def greedy_partial(slots: List[Slot], candidates: Dict[str, List[str]]) -> Dict[int, str]:
    """Best-effort fill when no complete solution exists: assign slots
    most-constrained-first, skipping any with no consistent candidate. Leaves the
    unresolved cells blank so scoring still credits the letters we did get."""
    grid: Dict[int, str] = {}
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

    def _ask_clues(self, patterns: Optional[Dict[str, str]] = None) -> Dict[str, List[str]]:
        """One batched LLM call for candidate answers to every slot. When
        ``patterns`` is given, only those slots are asked, with known letters shown
        (e.g. '_A_DY') so the model can respect the crossings."""
        by_id = {s.id: s for s in self.slots}
        lines = ["Solve this crossword. Give candidate answers for each clue.", ""]
        target = patterns.keys() if patterns else by_id.keys()
        for direction, label in (("A", "Across"), ("D", "Down")):
            entries = [sid for sid in target if sid.startswith(direction)]
            if not entries:
                continue
            lines.append(f"{label}:")
            for sid in entries:
                slot = by_id[sid]
                hint = f" pattern {patterns[sid]}" if patterns else ""
                lines.append(f"  {sid} ({slot.length}){hint}: {slot.clue}")
            lines.append("")
        lines.append('Respond as JSON mapping each id to up to '
                     f'{MAX_CANDIDATES_PER_SLOT} uppercase answers (best first), '
                     'each EXACTLY the stated length, e.g. {"A1": ["HEN"], "D2": ["EDDY"]}.')
        response = llm.complete_json("\n".join(lines), system=SYSTEM_PROMPT, max_tokens=1024)

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

    def _candidates(self, llm_cands: Dict[str, List[str]], dictionary: Dict[int, List[str]]) -> Dict[str, List[str]]:
        merged: Dict[str, List[str]] = {}
        for slot in self.slots:
            words = list(llm_cands.get(slot.id, []))
            seen = set(words)
            for word in dictionary.get(slot.length, []):
                if word not in seen:
                    words.append(word)
            merged[slot.id] = words
        return merged

    def play(self) -> None:
        dictionary = self.load_dictionary({s.length for s in self.slots})
        llm_cands = self._ask_clues()
        candidates = self._candidates(llm_cands, dictionary)

        grid = fill_grid(self.slots, candidates)
        if grid is None:
            # partial fill so far -> re-ask the unresolved slots with crossing hints
            self.grid = greedy_partial(self.slots, candidates)
            patterns = {s.id: self._pattern(s) for s in self.slots if "_" in self._pattern(s)}
            if patterns:
                extra = self._ask_clues(patterns)
                for sid, words in extra.items():
                    llm_cands.setdefault(sid, [])
                    llm_cands[sid] = words + [w for w in llm_cands[sid] if w not in words]
                candidates = self._candidates(llm_cands, dictionary)
                grid = fill_grid(self.slots, candidates)

        self.grid = grid if grid is not None else greedy_partial(self.slots, candidates)
        self._score()

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
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_solution(data)
