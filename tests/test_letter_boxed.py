import time

import pytest

from solvers.letter_boxed import LetterBoxedSolver as lb_module
from solvers.letter_boxed.LetterBoxedSolver import LetterBoxedSolver

# a 4x3 board whose 12 letters can be covered by a single alternating-side word
PUZZLE = {
    "id": 1,
    "sides": ["ABC", "DEF", "GHI", "JKL"],
    "dictionary": ["adgjbehkcfil"],
}


@pytest.fixture
def solver(monkeypatch):
    monkeypatch.setattr(lb_module, "fetch_game_data", lambda url: PUZZLE)
    return LetterBoxedSolver()


def test_get_next_side_adjacency(solver):
    assert solver.get_next_side("a", -1) == 0   # 'a' lives on side 0
    assert solver.get_next_side("a", 0) == -1   # cannot reuse the same side
    assert solver.get_next_side("d", 0) == 1


def test_validate_word_accepts_alternating_sides(solver):
    solver.validate_word("adg")  # a(0) d(1) g(2)
    assert solver.words.contains("adg")


def test_validate_word_rejects_same_side_and_short_words(solver):
    solver.validate_word("aad")  # two letters from side 0 in a row
    assert not solver.words.contains("aad")
    solver.validate_word("ad")   # shorter than MIN_LENGTH
    assert not solver.words.contains("ad")


def test_solves_full_board_with_single_word(solver):
    solver.validate_word("adgjbehkcfil")
    solver.get_valid_solutions(time.time())
    assert ["adgjbehkcfil"] in solver.answers[0]


def test_solving_uses_wordlist_not_nyt_dictionary(solver, monkeypatch, tmp_path):
    # a word present only in NYT's dictionary (not the human wordlist) must NOT
    # become a solution: we assess realistic human solving, not the answer list
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    # WORDS_FILE_PATH is absolute, so os.path.join('./', it) yields it verbatim
    monkeypatch.setattr(lb_module, "WORDS_FILE_PATH", str(empty))

    solver.load_solving_words()
    solver.get_valid_solutions(time.time())
    assert all(len(bucket) == 0 for bucket in solver.answers)
