import json
import os

import pytest

from solvers.strands import StrandsSolver as strands_module
from solvers.strands.StrandsSolver import (
    StrandsSolver,
    build_word_index,
    enumerate_placements,
    find_solutions_leftover,
    find_solutions_words,
    has_hamiltonian_path,
    is_spanning,
    neighbors,
    solve_with_c,
)

STRANDS_SO = os.path.join("src", "solvers", "strands", "StrandsSearch.so")


def test_neighbors_corner_and_center():
    assert set(neighbors(0, 3, 3)) == {1, 3, 4}          # top-left corner
    assert set(neighbors(4, 3, 3)) == {0, 1, 2, 3, 5, 6, 7, 8}  # center


def test_is_spanning():
    assert is_spanning({0, 2}, 3, 3)        # reaches left and right columns
    assert is_spanning({0, 6}, 3, 3)        # reaches top and bottom rows
    assert not is_spanning({4}, 3, 3)       # center only
    assert not is_spanning({0, 1}, 3, 3)    # touches top and left, not opposites


def test_has_hamiltonian_path():
    # a 3x3 grid; adjacency is king moves
    adj = {c: neighbors(c, 3, 3) for c in range(9)}
    assert has_hamiltonian_path({0, 1, 2}, adj)      # a straight line
    assert not has_hamiltonian_path({0, 2}, adj)     # two non-adjacent cells


def test_enumerate_finds_word_path():
    grid = ["ab", "cd"]  # cells: a=0 b=1 c=2 d=3
    word_set, prefixes = build_word_index(["abdc"])
    placements = enumerate_placements(grid, word_set, prefixes)
    assert ("abdc", frozenset({0, 1, 2, 3})) in placements


def test_find_solutions_words_exact_cover():
    grid = ["ab", "cd"]
    word_set, prefixes = build_word_index(["abdc"])
    placements = enumerate_placements(grid, word_set, prefixes)
    candidates, truncated = find_solutions_words(grid, placements)
    assert frozenset({"abdc"}) in candidates   # one word spans and covers all cells
    assert not truncated


def test_find_solutions_leftover_uses_spangram_path():
    # top row is a theme word; the bottom row is the leftover spangram strand
    grid = ["word", "abcd"]  # cells 0-3 = word, 4-7 = abcd
    word_set, prefixes = build_word_index(["word"])
    placements = enumerate_placements(grid, word_set, prefixes)
    candidates, _ = find_solutions_leftover(grid, placements, num_words=1)
    assert frozenset({"word"}) in candidates  # leftover {4,5,6,7} spans left-right


@pytest.mark.skipif(not os.path.exists(STRANDS_SO), reason="StrandsSearch.so not built")
def test_c_solver_finds_leftover_spangram():
    # bottom row "abcd" is the leftover spangram; "word" is the one theme word
    grid = ["word", "abcd"]
    word_set, prefixes = build_word_index(["word"])
    placements = enumerate_placements(grid, word_set, prefixes)
    result = solve_with_c(grid, placements, ["word"])
    assert result is not None
    solved, best_overlap, candidates = result
    assert solved is True
    assert best_overlap == 1


def test_solve_writes_solution_file(monkeypatch, tmp_path):
    monkeypatch.setattr(strands_module, "fetch_json", lambda url: {
        "id": 7,
        "startingBoard": ["word", "abcd"],
        "clue": "letters",
        "themeWords": ["WORD"],
        "spangram": "ABCD",   # the leftover bottom-row strand
    })
    solver = StrandsSolver("2026-07-21")
    monkeypatch.setattr(solver, "load_words", lambda: ["word"])
    solver.OUTPUT_DIRECTORY_PATH = str(tmp_path)
    solver.solve()

    data = json.load(open(f"{tmp_path}/2026-07-21.json"))
    assert data["solved"] is True
    assert data["theme_words_found"] == 1
    assert data["candidates"] >= 1
