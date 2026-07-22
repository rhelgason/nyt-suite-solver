import json
import time

from solvers.strands import StrandsSolver as strands_module
from solvers.strands.StrandsSolver import (
    StrandsSolver,
    build_word_index,
    enumerate_placements,
    find_solutions,
    is_spanning,
    neighbors,
)


def test_neighbors_corner_and_center():
    assert set(neighbors(0, 3, 3)) == {1, 3, 4}          # top-left corner
    assert set(neighbors(4, 3, 3)) == {0, 1, 2, 3, 5, 6, 7, 8}  # center


def test_is_spanning():
    assert is_spanning({0, 2}, 3, 3)        # reaches left and right columns
    assert is_spanning({0, 6}, 3, 3)        # reaches top and bottom rows
    assert not is_spanning({4}, 3, 3)       # center only
    assert not is_spanning({0, 1}, 3, 3)    # touches top and left, not opposites


def test_enumerate_finds_word_path():
    grid = ["ab", "cd"]  # cells: a=0 b=1 c=2 d=3
    word_set, prefixes = build_word_index(["abdc"])
    placements = enumerate_placements(grid, word_set, prefixes)
    # a0 -> b1 -> d3 -> c2 is a valid king-move path covering the whole grid
    assert ("abdc", frozenset({0, 1, 2, 3})) in placements


def test_find_solutions_covers_grid_with_spanning_word():
    grid = ["ab", "cd"]
    word_set, prefixes = build_word_index(["abdc"])
    placements = enumerate_placements(grid, word_set, prefixes)
    candidates, truncated = find_solutions(grid, placements, time.time())
    assert frozenset({"abdc"}) in candidates
    assert not truncated


def test_solve_writes_solution_file(monkeypatch, tmp_path):
    monkeypatch.setattr(strands_module, "fetch_json", lambda url: {
        "id": 7,
        "startingBoard": ["ab", "cd"],
        "clue": "letters",
        "themeWords": [],       # nothing but the spangram fits a 2x2 board
        "spangram": "ABDC",
    })
    solver = StrandsSolver("2026-07-21")
    monkeypatch.setattr(solver, "load_words", lambda: ["abdc"])
    solver.OUTPUT_DIRECTORY_PATH = str(tmp_path)
    solver.solve()

    data = json.load(open(f"{tmp_path}/2026-07-21.json"))
    assert data["spangram"] == "abdc"
    assert data["candidates"] >= 1
    assert data["spangram_matched"] is True  # {} | {"abdc"} == {"abdc"}
    assert isinstance(data["solved"], bool)
