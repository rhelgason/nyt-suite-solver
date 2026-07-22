import json
import math
import os

from solvers.wordle import WordleSolver as wordle_module
from solvers.wordle.WordleSolver import (
    WordleSolver,
    best_guess,
    expected_information,
    feedback,
    filter_candidates,
)


def test_feedback_all_green_when_equal():
    assert feedback("crate", "crate") == "ggggg"


def test_feedback_no_matches():
    assert feedback("fghij", "wxyzq") == "bbbbb"


def test_feedback_present_but_misplaced():
    assert feedback("tarot", "crate") == "yyybb"


def test_feedback_handles_duplicate_letters():
    assert feedback("lolly", "allot") == "yygbb"
    assert feedback("eerie", "abide") == "bbbyg"  # a green consumes the letter


def test_filter_candidates_keeps_only_consistent_words():
    candidates = ["crate", "grate", "plate", "brine"]
    observed = feedback("slate", "crate")  # -> "bbggg"
    assert set(filter_candidates(candidates, "slate", observed)) == {"crate", "grate"}


# a set of four words with disjoint letters: a guess touching all four letters
# distinguishes every word (2 bits), while guessing one of them does not
FOUR = ["aaaaa", "bbbbb", "ccccc", "ddddd"]


def test_expected_information_is_entropy_in_bits():
    # "abcde" produces a distinct pattern per word -> log2(4) = 2 bits
    assert abs(expected_information("abcde", FOUR) - 2.0) < 1e-9
    # "aaaaa" splits them 1 vs 3 -> ~0.811 bits
    expected = -(0.25 * math.log2(0.25) + 0.75 * math.log2(0.75))
    assert abs(expected_information("aaaaa", FOUR) - expected) < 1e-9


def test_easy_mode_may_pick_an_impossible_but_higher_information_guess():
    # easy mode (allowed = everything) prefers the max-information "abcde"
    assert best_guess(FOUR, FOUR + ["abcde"]) == "abcde"
    # hard mode (allowed = candidates only) must pick a real candidate
    assert best_guess(FOUR, FOUR) == "aaaaa"


def test_best_guess_shortcuts_when_two_left():
    assert best_guess(["crate", "brine"], ["crate", "brine"]) == "brine"  # sorted first


def _bare_solver(hard):
    solver = WordleSolver.__new__(WordleSolver)
    solver.hard = hard
    return solver


def test_play_solves_in_both_modes():
    words = ["slate", "crate", "grate", "plate", "brine", "shard", "pride"]
    for hard in (True, False):
        solver = _bare_solver(hard)
        solver.solution = "crate"
        guesses, solved = solver.play(words)
        assert solved
        assert guesses[-1] == "crate"
        assert len(guesses) <= 6


def test_play_fails_when_answer_outside_vocabulary():
    solver = _bare_solver(hard=True)
    solver.solution = "jazzy"
    _, solved = solver.play(["slate", "crate", "brine", "pound", "light"])
    assert not solved


def test_output_file_name_encodes_mode():
    easy = WordleSolver.__new__(WordleSolver)
    easy.hard, easy.ds = False, "2026-07-21"
    assert easy.output_file_name() == "2026-07-21_easy.json"
    hard = WordleSolver.__new__(WordleSolver)
    hard.hard, hard.ds = True, "2026-07-21"
    assert hard.output_file_name() == "2026-07-21_hard.json"


def test_solve_writes_solution_file(monkeypatch, tmp_path):
    monkeypatch.setattr(wordle_module, "fetch_json", lambda url: {"id": 42, "solution": "crate"})
    solver = WordleSolver("2026-07-21", hard=True)
    solver.OUTPUT_DIRECTORY_PATH = str(tmp_path)
    solver.solve()

    data = json.load(open(os.path.join(str(tmp_path), "2026-07-21_hard.json")))
    assert data["solved"] is True
    assert data["mode"] == "hard"
    assert data["solution"] == "crate"
    assert data["guesses"][-1] == "crate"
    assert data["num_guesses"] == len(data["guesses"])
