from datetime import datetime, timedelta
from display_utils import clear_terminal
from solvers.BaseSolver import BaseSolver
from solvers.scraping import fetch_json
from Spinner import Spinner
from time import time
from typing import Dict, FrozenSet, List, Set, Tuple

import os

BASE_URL = "https://www.nytimes.com/svc/strands/v2"
WORDS_FILE_PATH = "wordlist.txt"

# Strands theme answers are never shorter than this; excluding 2-3 letter words
# is the single biggest pruner for the exact-cover search.
MIN_WORD_LEN = 4

# A real board is a few long theme words plus the spangram, so cap the number of
# words in a candidate cover. This excludes the flood of all-short-word tilings
# and keeps the search tractable. (Puzzles with more theme words than this, or a
# multi-word/phrase spangram that is not a single dictionary word, are misses.)
MAX_WORDS_TOTAL = 9

# Search budgets: exact cover is NP-hard and we have no theme signal to guide us,
# so bound the work and report honestly when a cap is hit.
NODE_BUDGET = 2_000_000
MAX_CANDIDATES = 300
TIME_BUDGET_SECONDS = 20.0

# 8 king-move directions
DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

Placement = Tuple[str, FrozenSet[int]]  # (word, frozenset of cell ids)


def neighbors(cell: int, rows: int, cols: int) -> List[int]:
    r, c = divmod(cell, cols)
    out = []
    for dr, dc in DIRS:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            out.append(nr * cols + nc)
    return out


def build_word_index(words) -> Tuple[Set[str], Set[str]]:
    """Return (word set, prefix set) for words at least MIN_WORD_LEN long."""
    word_set, prefixes = set(), set()
    for word in words:
        if len(word) >= MIN_WORD_LEN and word.isalpha():
            word_set.add(word)
            for i in range(1, len(word) + 1):
                prefixes.add(word[:i])
    return word_set, prefixes


def enumerate_placements(grid: List[str], word_set: Set[str], prefixes: Set[str]) -> List[Placement]:
    """Every valid word and the exact cells it occupies, found by king-move DFS
    with prefix pruning (Boggle-style)."""
    rows, cols = len(grid), len(grid[0])
    found: Dict[Tuple[str, FrozenSet[int]], None] = {}

    def dfs(cell: int, current: str, path: List[int], visited: int) -> None:
        if len(current) >= MIN_WORD_LEN and current in word_set:
            found[(current, frozenset(path))] = None
        for nb in neighbors(cell, rows, cols):
            if visited & (1 << nb):
                continue
            nxt = current + grid[nb // cols][nb % cols]
            if nxt not in prefixes:
                continue
            path.append(nb)
            dfs(nb, nxt, path, visited | (1 << nb))
            path.pop()

    for start in range(rows * cols):
        ch = grid[start // cols][start % cols]
        if ch in prefixes:
            dfs(start, ch, [start], 1 << start)
    return [(w, cells) for (w, cells) in found]


def is_spanning(cells, rows: int, cols: int) -> bool:
    """A spangram must reach two opposite sides: top and bottom, or left and right."""
    top = bottom = left = right = False
    for cell in cells:
        r, c = divmod(cell, cols)
        top = top or r == 0
        bottom = bottom or r == rows - 1
        left = left or c == 0
        right = right or c == cols - 1
    return (top and bottom) or (left and right)


class _Budget:
    def __init__(self, start: float) -> None:
        self.nodes = 0
        self.start = start
        self.exhausted = False

    def tick(self) -> bool:
        self.nodes += 1
        if self.nodes > NODE_BUDGET or (time() - self.start) > TIME_BUDGET_SECONDS:
            self.exhausted = True
        return not self.exhausted


def find_solutions(grid: List[str], placements: List[Placement], start_time: float
                   ) -> Tuple[List[FrozenSet[str]], bool]:
    """Exact-cover search: partition all cells into disjoint valid words, at least
    one of which spans opposite sides (the spangram). Returns (candidate word
    sets, truncated). Capped word count keeps it to few-long-word covers."""
    rows, cols = len(grid), len(grid[0])
    full_mask = (1 << (rows * cols)) - 1

    masks = [0] * len(placements)
    spanning = [False] * len(placements)
    for i, (_, cells) in enumerate(placements):
        bits = 0
        for cell in cells:
            bits |= 1 << cell
        masks[i] = bits
        spanning[i] = is_spanning(cells, rows, cols)

    # longest words first so the few-long-words theme cover surfaces early
    order = sorted(range(len(placements)), key=lambda i: -len(placements[i][0]))
    cell_to_placements: Dict[int, List[int]] = {cell: [] for cell in range(rows * cols)}
    for idx in order:
        for cell in placements[idx][1]:
            cell_to_placements[cell].append(idx)

    candidates: List[FrozenSet[str]] = []
    seen: Set[FrozenSet[str]] = set()
    budget = _Budget(start_time)

    def dfs(covered: int, chosen: List[int], spanning_count: int) -> None:
        if budget.exhausted or len(candidates) >= MAX_CANDIDATES:
            return
        if not budget.tick():
            return
        if covered == full_mask:
            if spanning_count >= 1:  # a spangram is required
                words = frozenset(placements[i][0] for i in chosen)
                if words not in seen:
                    seen.add(words)
                    candidates.append(words)
            return
        if len(chosen) >= MAX_WORDS_TOTAL:
            return
        lowest = ~covered & full_mask
        target = (lowest & -lowest).bit_length() - 1
        for idx in cell_to_placements[target]:
            if covered & masks[idx]:
                continue
            chosen.append(idx)
            dfs(covered | masks[idx], chosen, spanning_count + (1 if spanning[idx] else 0))
            chosen.pop()
            if budget.exhausted or len(candidates) >= MAX_CANDIDATES:
                return

    dfs(0, [], 0)
    return candidates, budget.exhausted


class StrandsSolver(BaseSolver):
    OUTPUT_DIRECTORY_PATH = "solutions/strands"

    def __init__(self, ds: str = None) -> None:
        super().__init__(ds)
        self.grid: List[str] = []
        self.clue: str = ""
        self.theme_words: List[str] = []
        self.spangram: str = ""
        self.scrape_puzzle()

    def scrape_puzzle(self) -> None:
        fetching_str = "Fetching puzzle from NYT website..."
        clear_terminal()
        with Spinner(fetching_str):
            data = fetch_json(f"{BASE_URL}/{self.ds}.json")
            self.puzzle_id = data["id"]
            self.grid = [row.lower() for row in data["startingBoard"]]
            self.clue = data.get("clue", "")
            self.theme_words = [w.lower() for w in data["themeWords"]]
            self.spangram = data["spangram"].lower()
        clear_terminal()
        print(fetching_str + " done!")

    def load_words(self):
        with open(os.path.join("./", WORDS_FILE_PATH), "r") as f:
            return [line.strip().lower() for line in f]

    def solve(self) -> None:
        date = datetime.strptime(self.ds, "%Y-%m-%d")
        print(f"Solving Strands for {date.strftime('%B %d, %Y')} (theme: {self.clue}):\n")
        print("\n".join(self.grid).upper())

        start = time()
        word_set, prefixes = build_word_index(self.load_words())
        placements = enumerate_placements(self.grid, word_set, prefixes)
        candidates, truncated = find_solutions(self.grid, placements, start)
        end = time()

        theme_set = frozenset(self.theme_words)
        # "solved" = some candidate cover recovers every theme word. The spangram
        # is often a multi-word phrase (not one dictionary word), so we do not
        # require matching it exactly; we note separately when we do.
        solved = any(theme_set <= cand for cand in candidates)
        spangram_matched = any(cand == theme_set | {self.spangram} for cand in candidates)
        best_overlap = max((len(cand & theme_set) for cand in candidates), default=0)

        if solved:
            note = " (spangram too)" if spangram_matched else ""
            print(f"\nSolved! Recovered all {len(theme_set)} theme words{note} among {len(candidates)} cover(s).")
        else:
            print(f"\nNot solved. Best cover recovered {best_overlap}/{len(theme_set)} theme words "
                  f"across {len(candidates)} candidate(s)" + (" (search truncated)." if truncated else "."))

        self.write_solved_puzzle(candidates, solved, spangram_matched, best_overlap, truncated, start, end)

    def write_solved_puzzle(self, candidates, solved, spangram_matched, best_overlap, truncated, start, end) -> None:
        data = {
            "puzzle_id": self.puzzle_id,
            "ds": self.ds,
            "clue": self.clue,
            "theme_words": self.theme_words,
            "spangram": self.spangram,
            "solved": solved,
            "spangram_matched": spangram_matched,
            "theme_words_found": best_overlap,
            "theme_words_total": len(self.theme_words),
            "candidates": len(candidates),
            "truncated": truncated,
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_solution(data)
