import json
import os

import pytest

from menu_options import SudokuDifficultyOptions
from solvers.sudoku import SudokuSolver as sk_module
from solvers.sudoku.SudokuSolver import SudokuSolver

SO_PATH = os.path.join("src", "solvers", "sudoku", "DancingLinks.so")

pytestmark = pytest.mark.skipif(
    not os.path.exists(SO_PATH),
    reason="DancingLinks.so not built; run `make build-sudoku` first",
)


def _load_fixture():
    with open(os.path.join("solutions", "sudoku", "2026-07-21_hard.json")) as f:
        d = json.load(f)
    puzzle = [int(x) for x in d["input_puzzle"].split(",")]
    return puzzle, d["solved_puzzle"], d["puzzle_id"]


def _make_game_data(puzzle, puzzle_id):
    return {"hard": {"puzzle_id": puzzle_id, "puzzle_data": {"puzzle": puzzle}}}


def _is_valid_solution(grid):
    full = set(range(1, 10))
    for i in range(9):
        if set(grid[i]) != full:
            return False
        if {grid[r][i] for r in range(9)} != full:
            return False
    for bi in range(0, 9, 3):
        for bj in range(0, 9, 3):
            box = [grid[bi + a][bj + b] for a in range(3) for b in range(3)]
            if set(box) != full:
                return False
    return True


def test_reshape_input_board():
    solver = SudokuSolver.__new__(SudokuSolver)  # skip the network __init__
    board = solver.reshape_input_board(list(range(81)))
    assert board.shape == (9, 9)
    assert board[0][0] == 0
    assert board[8][8] == 80


def test_solves_known_board(monkeypatch, tmp_path):
    puzzle, expected, pid = _load_fixture()
    monkeypatch.setattr(sk_module, "fetch_game_data", lambda url: _make_game_data(puzzle, pid))
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")
    solver = SudokuSolver(SudokuDifficultyOptions.HARD)
    solver.OUTPUT_DIRECTORY_PATH = str(tmp_path)
    solver.solve()

    got = ",".join(",".join(str(x) for x in row) for row in solver.solved_puzzle)
    assert got == expected
    assert _is_valid_solution(solver.solved_puzzle.tolist())


def test_invalid_board_raises(monkeypatch):
    bad = [0] * 81
    bad[0] = 5
    bad[1] = 5  # duplicate value in the first row
    monkeypatch.setattr(sk_module, "fetch_game_data", lambda url: _make_game_data(bad, 1))
    with pytest.raises(Exception):
        SudokuSolver(SudokuDifficultyOptions.HARD)
