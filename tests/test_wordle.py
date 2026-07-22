import json
import os

from solvers.wordle import WordleSolver as wordle_module
from solvers.wordle.WordleSolver import (
    WordleSolver,
    choose_guess,
    feedback,
    filter_candidates,
)


def test_feedback_all_green_when_equal():
    assert feedback("crate", "crate") == "ggggg"


def test_feedback_no_matches():
    assert feedback("fghij", "wxyzq") == "bbbbb"


def test_feedback_present_but_misplaced():
    # every letter of "tarot" is in "crate" but none are correctly placed
    # t(y) a(y) r(y) o(b) t(b, second t has no match left)
    assert feedback("tarot", "crate") == "yyybb"


def test_feedback_handles_duplicate_letters():
    # guessing "lolly" against "allot": one l is green, one l is yellow, the
    # third l gets nothing left, and the extra o/y are black
    assert feedback("lolly", "allot") == "yygbb"
    # a green consumes the letter so a later duplicate is not also marked
    assert feedback("eerie", "abide") == "bbbyg"


def test_filter_candidates_keeps_only_consistent_words():
    candidates = ["crate", "grate", "plate", "brine"]
    observed = feedback("slate", "crate")  # -> "bbggg"
    kept = filter_candidates(candidates, "slate", observed)
    assert set(kept) == {"crate", "grate"}  # plate has l green, brine differs


def test_choose_guess_is_deterministic_and_in_pool():
    pool = ["crane", "slate", "brine", "pound", "light", "grate"]
    first = choose_guess(pool)
    assert first in pool
    assert choose_guess(pool) == first  # deterministic


def test_play_solves_when_answer_in_vocabulary():
    solver = WordleSolver.__new__(WordleSolver)
    solver.solution = "crate"
    guesses, solved = solver.play(["slate", "crate", "grate", "plate", "brine"])
    assert solved
    assert guesses[-1] == "crate"
    assert len(guesses) <= 6


def test_play_fails_when_answer_outside_vocabulary():
    solver = WordleSolver.__new__(WordleSolver)
    solver.solution = "jazzy"  # not in the candidate pool below
    guesses, solved = solver.play(["slate", "crate", "brine", "pound", "light"])
    assert not solved


def test_solve_writes_solution_file(monkeypatch, tmp_path):
    monkeypatch.setattr(wordle_module, "fetch_json", lambda url: {"id": 42, "solution": "crate"})
    solver = WordleSolver("2026-07-21")
    solver.OUTPUT_DIRECTORY_PATH = str(tmp_path)
    solver.solve()

    data = json.load(open(os.path.join(str(tmp_path), "2026-07-21.json")))
    assert data["solved"] is True
    assert data["solution"] == "crate"
    assert data["guesses"][-1] == "crate"
    assert data["num_guesses"] == len(data["guesses"])
