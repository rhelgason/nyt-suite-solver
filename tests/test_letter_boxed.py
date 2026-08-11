import json
import time
from datetime import datetime

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


def test_past_date_fetches_the_json_archive(monkeypatch):
    # a date-suffixed HTML page 404s, so past boards must come from the archive
    # endpoint -- which carries that day's own dictionary, letting it be scored
    calls = {}

    def fake_json(url):
        calls["url"] = url
        return dict(PUZZLE, printDate="2025-06-01")

    monkeypatch.setattr(lb_module, "fetch_json", fake_json)
    monkeypatch.setattr(lb_module, "fetch_game_data", lambda url: pytest.fail("used the HTML page for a past date"))

    s = LetterBoxedSolver("2025-06-01")
    assert calls["url"] == "https://www.nytimes.com/svc/letter-boxed/v1/2025-06-01.json"
    assert s.valid_words.contains("adgjbehkcfil")


def test_archive_date_mismatch_is_an_error(monkeypatch):
    # solving the wrong day would quietly write bad history, so refuse it
    monkeypatch.setattr(lb_module, "fetch_json", lambda url: dict(PUZZLE, printDate="2025-06-02"))
    with pytest.raises(lb_module.PuzzleDataNotFound):
        LetterBoxedSolver("2025-06-01")


def test_today_still_uses_the_puzzle_page(monkeypatch):
    # the unattended daily run keeps the fetch path it has always used
    today = datetime.today().date().strftime("%Y-%m-%d")
    monkeypatch.setattr(lb_module, "fetch_game_data", lambda url: PUZZLE)
    monkeypatch.setattr(lb_module, "fetch_json", lambda url: pytest.fail("used the archive for today"))
    assert LetterBoxedSolver(today).ds == today


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


def test_deepens_only_until_a_solution_is_found(solver):
    # the board is solvable in one word, so the search must not go on to
    # enumerate the (vastly more numerous) multi-word solutions
    solver.validate_word("adgjbehkcfil")
    solver.validate_word("adg")
    solver.validate_word("gjbehkcfil")
    solver.get_valid_solutions(time.time())
    assert ["adgjbehkcfil"] in solver.answers[0]
    assert all(len(bucket) == 0 for bucket in solver.answers[1:])


def test_finds_multi_word_solution_when_no_single_word_exists(solver):
    # nothing covers the board alone, so deepening should reach the 2-word answer
    solver.validate_word("adg")
    solver.validate_word("gjbehkcfil")
    solver.get_valid_solutions(time.time())
    assert ["adg", "gjbehkcfil"] in solver.answers[1]


def test_unsolved_board_writes_null_not_a_sentinel(solver, tmp_path, monkeypatch):
    # a board our wordlist cannot solve must record null: a sentinel like
    # sys.maxsize silently poisons the lifetime averages in stats.py
    monkeypatch.setattr(solver, "OUTPUT_DIRECTORY_PATH", str(tmp_path))
    solver.answers = [[] for _ in range(lb_module.MAX_WORDS)]
    solver.write_solved_puzzle(0.0, 1.0)

    written = json.loads((tmp_path / solver.output_file_name()).read_text())
    assert written["shortest_answer_length"] is None
    assert written["valid_answers"] == []


def test_logged_answers_are_capped_but_totals_preserved(solver, tmp_path, monkeypatch):
    # a deep search can find tens of thousands of solutions; the committed file
    # keeps a sample plus the true count so it cannot grow without bound
    monkeypatch.setattr(solver, "OUTPUT_DIRECTORY_PATH", str(tmp_path))
    monkeypatch.setattr(lb_module, "MAX_LOGGED_ANSWERS", 5)
    solver.answers = [[["adgjbehkcfil"] for _ in range(20)]] + [[] for _ in range(lb_module.MAX_WORDS - 1)]
    solver.write_solved_puzzle(0.0, 1.0)

    written = json.loads((tmp_path / solver.output_file_name()).read_text())
    assert len(written["valid_answers"]) == 5
    assert written["num_valid_answers"] == 20
    assert written["shortest_answer_length"] == 1


def test_search_stops_at_the_time_budget(solver, monkeypatch):
    # an exhausted budget must abandon the search rather than hang the daily run
    monkeypatch.setattr(lb_module, "SEARCH_BUDGET_SECONDS", -1)
    solver.validate_word("adgjbehkcfil")
    solver.get_valid_solutions(time.time())
    assert all(len(bucket) == 0 for bucket in solver.answers)


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
