import pytest

from solvers.spelling_bee import SpellingBeeSolver as sb_module
from solvers.spelling_bee.SpellingBeeSolver import SpellingBeeRanks, SpellingBeeSolver

PUZZLE = {
    "today": {
        "id": 5,
        "centerLetter": "a",
        "validLetters": ["a", "b", "c", "d", "e", "f", "g"],
        "answers": ["abcdefg", "aabb", "cafe"],
    }
}


@pytest.fixture
def solver(monkeypatch):
    monkeypatch.setattr(sb_module, "fetch_game_data", lambda url: PUZZLE)
    return SpellingBeeSolver("2024-01-01")


def test_validate_word_classifies_pangram_and_word(solver):
    solver.validate_word("abcdefg")  # all seven letters -> pangram
    solver.validate_word("aabb")     # subset including center -> regular word
    assert solver.pangrams.contains("abcdefg")
    assert solver.words.contains("aabb")


def test_validate_word_rejects_invalid_words(solver):
    solver.validate_word("bcd")  # missing center letter 'a'
    solver.validate_word("abx")  # 'x' is not a valid letter
    solver.validate_word("abc")  # shorter than MIN_LENGTH
    assert solver.words.to_list() == []
    assert solver.pangrams.to_list() == []


def test_score_word(solver):
    assert solver.score_word("aabb") == 1        # four-letter word => 1 point
    solver.pangrams.add_word("abcdefg")
    assert solver.score_word("abcdefg") == 4 + 7  # length points + pangram bonus


def test_write_performance_full_score(solver):
    data = {"valid_answers": ["cafe"], "missed_answers": []}
    solver.write_performance(data)
    assert data["percentage"] == 100
    assert data["rank"] == SpellingBeeRanks.QUEEN_BEE.name


def test_write_performance_handles_zero_total(solver):
    data = {"valid_answers": [], "missed_answers": []}
    solver.write_performance(data)  # must not raise ZeroDivisionError
    assert data["percentage"] == 0
    assert data["rank"] == SpellingBeeRanks.BEGINNER.name
