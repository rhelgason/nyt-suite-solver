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
    assert "## Lifetime results" in section
    assert "**4** puzzles solved across 3 games (through 2026-01-02)" in section
    assert "avg score **75.0%**" in section                 # (100 + 50) / 2
    assert "Queen Bee on **50%** of puzzles" in section      # 1 of 2
    assert "**100%** solved" in section                      # letter boxed + sudoku
    # cumulative chart is referenced as a committed SVG image (2 distinct dates)
    assert "![Cumulative puzzles solved by game](stats/cumulative_solves.svg)" in section
    # score histogram replaces the rank chart
    assert "Spelling Bee score distribution" in section


def test_cumulative_chart_omitted_for_single_date(tmp_path):
    root = str(tmp_path)
    _write(root, "spelling_bee", "2026-01-01.json", {"ds": "2026-01-01", "percentage": 100, "rank": "QUEEN_BEE"})
    section = build_section(root)
    # only one date and one score -> neither chart is drawn
    assert "cumulative_solves.svg" not in section
    assert "```mermaid" not in section


def test_write_assets_emits_valid_svg(tmp_path):
    import xml.etree.ElementTree as ET

    from stats import cumulative_solves_svg, load_game

    root = str(tmp_path)
    _write(root, "spelling_bee", "2026-01-01.json", {"ds": "2026-01-01", "percentage": 100, "rank": "QUEEN_BEE"})
    _write(root, "sudoku", "2026-01-02_hard.json", {"ds": "2026-01-02", "solved_puzzle": "1", "solve_time": "0:00:00.0001"})
    games = {g: load_game(root, g) for g in ("spelling_bee", "letter_boxed", "sudoku")}

    svg = cumulative_solves_svg(games)
    ET.fromstring(svg)  # must be well-formed XML
    assert "Spelling Bee" in svg and "Letter Boxed" in svg and "Sudoku" in svg  # legend labels
    assert svg.count("<polyline") == 3  # one line per game


def test_score_histogram_buckets(tmp_path):
    root = str(tmp_path)
    scores = {"2026-01-01": 100, "2026-01-02": 97, "2026-01-03": 92, "2026-01-04": 100}
    for ds, pct in scores.items():
        _write(root, "spelling_bee", f"{ds}.json", {"ds": ds, "percentage": pct, "rank": "GENIUS"})
    section = build_section(root)
    assert "Spelling Bee score distribution" in section
    # leading empty buckets (<80, 80-89) are trimmed; range starts at 90-94
    assert '"90-94", "95-99", "100"' in section
    assert "bar [1, 1, 2]" in section  # 92 | 97 | (100, 100)


def test_build_section_empty(tmp_path):
    section = build_section(str(tmp_path))
    assert "_No puzzles solved yet._" in section


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
