from datetime import datetime, timedelta
from display_utils import clear_terminal
from solvers.BaseSolver import BaseSolver
from solvers.scraping import fetch_json
from Spinner import Spinner
from time import time
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

import os

BASE_URL = "https://www.nytimes.com/svc/strands/v2"
WORDS_FILE_PATH = "wordlist.txt"

# Strands theme answers are never shorter than this; excluding 2-3 letter words
# is the single biggest pruner for the exact-cover search.
MIN_WORD_LEN = 4

# A real board is a few long theme words plus the spangram, so cap the number of
# words in a candidate cover. This excludes the flood of all-short-word tilings.
MAX_WORDS_TOTAL = 9

# The leftover (fallback) search covers the board with the exact theme-word count
# and treats the remaining cells as the spangram strand (which need not be a
# dictionary word, so phrase spangrams like "pie in the sky" work).
MAX_SPANGRAM_CELLS = 16
HAM_PATH_STEP_BUDGET = 100_000

# Search budgets: this is NP-hard with no theme signal, so bound the work and
# report honestly when a cap is hit. We try a fast exact-cover-by-words pass
# first, then fall back to the slower leftover-path search only if it did not
# already recover the theme words.
NODE_BUDGET = 12_000_000
MAX_CANDIDATES = 20_000
WORDS_TIME_BUDGET = 20.0
LEFTOVER_TIME_BUDGET = 30.0

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


def has_hamiltonian_path(cells: Set[int], adj: Dict[int, List[int]]) -> bool:
    """Whether the cells can be traced as one continuous strand (a single path
    visiting every cell once over king adjacency). Bounded by a step budget."""
    n = len(cells)
    if n <= 1:
        return n == 1
    steps = [0]

    def extend(cell: int, seen: Set[int]) -> bool:
        if len(seen) == n:
            return True
        steps[0] += 1
        if steps[0] > HAM_PATH_STEP_BUDGET:
            return False
        for nb in adj[cell]:
            if nb in cells and nb not in seen:
                seen.add(nb)
                if extend(nb, seen):
                    return True
                seen.remove(nb)
        return False

    for start in cells:
        if extend(start, {start}):
            return True
        if steps[0] > HAM_PATH_STEP_BUDGET:
            return False
    return False


class _Budget:
    def __init__(self, time_budget: float, node_budget: int = NODE_BUDGET) -> None:
        self.nodes = 0
        self.start = time()
        self.time_budget = time_budget
        self.node_budget = node_budget
        self.exhausted = False

    def tick(self) -> bool:
        self.nodes += 1
        if self.nodes > self.node_budget or (time() - self.start) > self.time_budget:
            self.exhausted = True
        return not self.exhausted


def _mask_to_cells(mask: int, n: int) -> Set[int]:
    return {c for c in range(n) if mask >> c & 1}


def _placement_masks(placements: List[Placement], n: int):
    masks = [0] * len(placements)
    for i, (_, cells) in enumerate(placements):
        bits = 0
        for cell in cells:
            bits |= 1 << cell
        masks[i] = bits
    # longest words first so the few-long-words theme cover surfaces early
    order = sorted(range(len(placements)), key=lambda i: -len(placements[i][0]))
    cell_to_placements: Dict[int, List[int]] = {cell: [] for cell in range(n)}
    for idx in order:
        for cell in placements[idx][1]:
            cell_to_placements[cell].append(idx)
    return masks, cell_to_placements


def _cell_order(rows: int, cols: int) -> List[int]:
    """Most-constrained cells first: corners (3 neighbours), then edges (5), then
    interior (8). Branching on these first prunes the search like an MRV
    heuristic would, but is precomputed so it costs nothing per node."""
    return sorted(range(rows * cols), key=lambda c: (len(neighbors(c, rows, cols)), c))


def _first_unassigned(cell_order: List[int], assigned: int) -> int:
    for cell in cell_order:
        if not (assigned >> cell & 1):
            return cell
    return -1


def find_solutions_words(grid: List[str], placements: List[Placement],
                         target: Optional[FrozenSet[str]] = None
                         ) -> Tuple[List[FrozenSet[str]], bool]:
    """Fast pass: exact-cover every cell with valid words, at least one spanning
    (the spangram is a single dictionary word or a chain of them). Stops early
    once ``target`` (the theme words) is recovered. Returns (candidate word sets,
    truncated)."""
    rows, cols = len(grid), len(grid[0])
    n = rows * cols
    full_mask = (1 << n) - 1
    masks, cell_to_placements = _placement_masks(placements, n)
    spanning = [is_spanning(cells, rows, cols) for _, cells in placements]

    candidates: List[FrozenSet[str]] = []
    seen: Set[FrozenSet[str]] = set()
    budget = _Budget(WORDS_TIME_BUDGET)
    found = [False]

    def dfs(covered: int, chosen: List[int], spanning_count: int) -> None:
        if found[0] or budget.exhausted or len(candidates) >= MAX_CANDIDATES:
            return
        if not budget.tick():
            return
        if covered == full_mask:
            if spanning_count >= 1:
                words = frozenset(placements[i][0] for i in chosen)
                if words not in seen:
                    seen.add(words)
                    candidates.append(words)
                    if target is not None and target <= words:
                        found[0] = True
            return
        if len(chosen) >= MAX_WORDS_TOTAL:
            return
        lowest = ~covered & full_mask
        cell = (lowest & -lowest).bit_length() - 1
        for idx in cell_to_placements[cell]:
            if covered & masks[idx]:
                continue
            chosen.append(idx)
            dfs(covered | masks[idx], chosen, spanning_count + (1 if spanning[idx] else 0))
            chosen.pop()
            if found[0] or budget.exhausted or len(candidates) >= MAX_CANDIDATES:
                return

    dfs(0, [], 0)
    return candidates, budget.exhausted and not found[0]


def find_solutions_leftover(grid: List[str], placements: List[Placement], num_words: int,
                            target: Optional[FrozenSet[str]] = None
                            ) -> Tuple[List[FrozenSet[str]], bool]:
    """Fallback: partition the board into exactly ``num_words`` theme words plus a
    leftover spangram. The leftover cells (everything not covered by a theme word)
    must form one connected king-path spanning opposite sides; it is never
    dictionary-matched, so phrase spangrams work. ``num_words`` is the theme-word
    count NYT shows the player, which prunes the search hard. Stops early once
    ``target`` is recovered.

    Returns (candidate theme-word sets, truncated)."""
    rows, cols = len(grid), len(grid[0])
    n = rows * cols
    full_mask = (1 << n) - 1
    adj = {cell: neighbors(cell, rows, cols) for cell in range(n)}
    masks, cell_to_placements = _placement_masks(placements, n)
    cell_order = _cell_order(rows, cols)

    candidates: List[FrozenSet[str]] = []
    seen: Set[FrozenSet[str]] = set()
    budget = _Budget(LEFTOVER_TIME_BUDGET)
    found = [False]

    def record(covered: int, chosen: List[int]) -> None:
        spangram = _mask_to_cells(full_mask & ~covered, n)
        if not (0 < len(spangram) <= MAX_SPANGRAM_CELLS):
            return
        if is_spanning(spangram, rows, cols) and has_hamiltonian_path(spangram, adj):
            words = frozenset(placements[i][0] for i in chosen)
            if words not in seen:
                seen.add(words)
                candidates.append(words)
                if target is not None and target <= words:
                    found[0] = True

    def dfs(covered: int, reserved: int, chosen: List[int]) -> None:
        if found[0] or budget.exhausted or len(candidates) >= MAX_CANDIDATES:
            return
        if not budget.tick():
            return
        if len(chosen) == num_words:
            record(covered, chosen)  # everything uncovered becomes the spangram
            return
        assigned = covered | reserved
        if assigned == full_mask:
            return  # ran out of cells before placing all theme words
        cell = _first_unassigned(cell_order, assigned)
        # Branch 1: cover the target cell with a theme word
        for idx in cell_to_placements[cell]:
            if masks[idx] & assigned:
                continue
            chosen.append(idx)
            dfs(covered | masks[idx], reserved, chosen)
            chosen.pop()
            if found[0] or budget.exhausted or len(candidates) >= MAX_CANDIDATES:
                return
        # Branch 2: the target cell belongs to the spangram instead
        if bin(reserved).count("1") < MAX_SPANGRAM_CELLS:
            dfs(covered, reserved | (1 << cell), chosen)

    dfs(0, 0, [])
    return candidates, budget.exhausted and not found[0]


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
        # only words whose letters all appear on the board can ever be placed, so
        # drop the rest up front to keep the trie/prefix set small and enumeration fast
        grid_letters = set("".join(self.grid))
        with open(os.path.join("./", WORDS_FILE_PATH), "r") as f:
            return [w for w in (line.strip().lower() for line in f) if set(w) <= grid_letters]

    def solve(self) -> None:
        date = datetime.strptime(self.ds, "%Y-%m-%d")
        print(f"Solving Strands for {date.strftime('%B %d, %Y')} (theme: {self.clue}):\n")
        print("\n".join(self.grid).upper())

        start = time()
        word_set, prefixes = build_word_index(self.load_words())
        placements = enumerate_placements(self.grid, word_set, prefixes)
        theme_set = frozenset(self.theme_words)

        # Fast pass: cover the whole board with words (spangram as dictionary
        # word(s)). Fall back to the slower leftover-path search only if that did
        # not already recover the theme words, since it also handles phrase
        # spangrams. NYT shows the theme-word count, so we use it to prune.
        candidates, truncated = find_solutions_words(self.grid, placements, target=theme_set)
        if not any(theme_set <= cand for cand in candidates):
            leftover, trunc_l = find_solutions_leftover(
                self.grid, placements, len(self.theme_words), target=theme_set)
            candidates = candidates + leftover
            truncated = truncated or trunc_l
        end = time()

        # "solved" = some candidate cover recovers every theme word (the spangram
        # is then the remaining strand).
        solved = any(theme_set <= cand for cand in candidates)
        best_overlap = max((len(cand & theme_set) for cand in candidates), default=0)

        if solved:
            print(f"\nSolved! Recovered all {len(theme_set)} theme words among {len(candidates)} cover(s).")
        else:
            print(f"\nNot solved. Best cover recovered {best_overlap}/{len(theme_set)} theme words "
                  f"across {len(candidates)} candidate(s)" + (" (search truncated)." if truncated else "."))

        self.write_solved_puzzle(candidates, solved, best_overlap, truncated, start, end)

    def write_solved_puzzle(self, candidates, solved, best_overlap, truncated, start, end) -> None:
        data = {
            "puzzle_id": self.puzzle_id,
            "ds": self.ds,
            "clue": self.clue,
            "theme_words": self.theme_words,
            "spangram": self.spangram,
            "solved": solved,
            "theme_words_found": best_overlap,
            "theme_words_total": len(self.theme_words),
            "candidates": len(candidates),
            "truncated": truncated,
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_solution(data)
