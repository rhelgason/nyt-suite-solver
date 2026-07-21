import json
import os

from stats import START_MARKER, END_MARKER, as_list, build_section, update_readme


def _write(root, game, name, data):
    directory = os.path.join(root, game)
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, name), "w") as f:
        json.dump(data, f)


def test_as_list_handles_list_and_legacy_string():
    assert as_list([["a"], ["b"]]) == [["a"], ["b"]]
    assert as_list("[['a'], ['b']]") == [["a"], ["b"]]  # legacy stringified format
    assert as_list("not a list") == []
    assert as_list(None) == []


def test_build_section_summarizes_each_game(tmp_path):
    root = str(tmp_path)
    _write(root, "spelling_bee", "2026-01-01.json", {"ds": "2026-01-01", "percentage": 100, "rank": "QUEEN_BEE"})
    _write(root, "spelling_bee", "2026-01-02.json", {"ds": "2026-01-02", "percentage": 50, "rank": "AMAZING"})
    _write(root, "letter_boxed", "2026-01-01.json",
           {"ds": "2026-01-01", "valid_answers": [["a", "b"], ["c", "d"]], "shortest_answer_length": 2})
    _write(root, "sudoku", "2026-01-01_hard.json",
           {"ds": "2026-01-01", "solved_puzzle": "1,2", "solve_time": "0:00:00.000200"})

    section = build_section(root)
    assert "## Latest results" in section
    assert "Puzzles solved: **2**" in section       # spelling bee count
    assert "avg **75.0%**" in section                # (100 + 50) / 2
    assert "```mermaid" in section                   # trend chart rendered
    assert "Solved successfully: **1/1**" in section  # sudoku


def test_build_section_empty(tmp_path):
    section = build_section(str(tmp_path))
    assert "no puzzles yet" in section
    assert section.count("_No puzzles solved yet._") == 3


def test_update_readme_replaces_between_markers():
    text = f"intro\n\n{START_MARKER}\nOLD\n{END_MARKER}\n\noutro\n"
    out = update_readme(text, "NEW")
    assert "OLD" not in out
    assert "NEW" in out
    assert out.startswith("intro")
    assert out.rstrip().endswith("outro")


def test_update_readme_appends_when_missing():
    out = update_readme("just intro\n", "SECTION")
    assert START_MARKER in out and END_MARKER in out
    assert "SECTION" in out
