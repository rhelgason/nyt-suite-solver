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


def test_build_section_table_and_chart(tmp_path):
    root = str(tmp_path)
    _write(root, "spelling_bee", "2026-01-01.json", {"ds": "2026-01-01", "percentage": 100, "rank": "QUEEN_BEE"})
    _write(root, "spelling_bee", "2026-01-02.json", {"ds": "2026-01-02", "percentage": 50, "rank": "AMAZING"})
    _write(root, "letter_boxed", "2026-01-01.json",
           {"ds": "2026-01-01", "valid_answers": [["a", "b"], ["c", "d"]], "shortest_answer_length": 2})
    _write(root, "sudoku", "2026-01-01_hard.json",
           {"ds": "2026-01-01", "solved_puzzle": "1,2", "solve_time": "0:00:00.000200"})
    _write(root, "wordle", "2026-01-02_easy.json", {"ds": "2026-01-02", "mode": "easy", "solved": True, "num_guesses": 3})
    _write(root, "wordle", "2026-01-02_hard.json", {"ds": "2026-01-02", "mode": "hard", "solved": True, "num_guesses": 4})

    section = build_section(root)
    assert "## Lifetime results" in section
    assert "**6** puzzles solved across 4 games (through 2026-01-02)" in section
    # the lifetime table is a centered HTML table (markdown tables cannot be centered)
    assert '<div align="center">' in section
    assert "<tr><th>Game</th><th>Puzzles</th><th>Avg score</th><th>p90 runtime</th></tr>" in section
    assert "<tr><td>Spelling Bee</td><td>2</td><td>75.0%</td><td>n/a</td></tr>" in section  # (100 + 50) / 2
    assert "<tr><td>Letter Boxed</td><td>1</td><td>2.0 words</td><td>n/a</td></tr>" in section
    assert "<tr><td>Sudoku</td><td>1</td><td>100%</td><td>0.20 ms</td></tr>" in section
    assert "<tr><td>Wordle (easy)</td><td>1</td><td>3.0 guesses</td><td>n/a</td></tr>" in section
    assert "<tr><td>Wordle (hard)</td><td>1</td><td>4.0 guesses</td><td>n/a</td></tr>" in section


def test_score_pie_svg(tmp_path):
    import xml.etree.ElementTree as ET

    from stats import load_game, score_pie_svg, summarize_spelling_bee

    root = str(tmp_path)
    scores = {"2026-01-01": 100, "2026-01-02": 97, "2026-01-03": 92, "2026-01-04": 100}
    for ds, pct in scores.items():
        _write(root, "spelling_bee", f"{ds}.json", {"ds": ds, "percentage": pct, "rank": "GENIUS"})

    svg = score_pie_svg(summarize_spelling_bee(load_game(root, "spelling_bee")))
    ET.fromstring(svg)  # well-formed XML
    # three non-empty buckets (90-94, 95-99, 100) -> three pie slices + legend rows
    assert svg.count("<path") == 3
    assert "100: 2 (50%)" in svg  # two perfect scores of four puzzles


def test_word_count_pie_svg(tmp_path):
    import xml.etree.ElementTree as ET

    from stats import load_game, summarize_letter_boxed, word_count_pie_svg

    root = str(tmp_path)
    _write(root, "letter_boxed", "2026-01-01.json", {"ds": "2026-01-01", "shortest_answer_length": 1})
    _write(root, "letter_boxed", "2026-01-02.json", {"ds": "2026-01-02", "shortest_answer_length": 2})
    _write(root, "letter_boxed", "2026-01-03.json", {"ds": "2026-01-03", "shortest_answer_length": 2})

    svg = word_count_pie_svg(summarize_letter_boxed(load_game(root, "letter_boxed")))
    ET.fromstring(svg)  # well-formed XML
    assert svg.count("<path") == 2               # "1 word" and "2 words" slices
    assert "1 word: 1 (33%)" in svg
    assert "2 words: 2 (67%)" in svg


def test_unsolved_letter_boxed_is_shown_not_averaged(tmp_path):
    import xml.etree.ElementTree as ET

    from stats import load_game, summarize_letter_boxed, word_count_pie_svg

    root = str(tmp_path)
    _write(root, "letter_boxed", "2026-01-01.json", {"ds": "2026-01-01", "shortest_answer_length": 2})
    _write(root, "letter_boxed", "2026-01-02.json", {"ds": "2026-01-02", "shortest_answer_length": None})
    # an older run recorded sys.maxsize instead of null; it must not be averaged
    _write(root, "letter_boxed", "2026-01-03.json", {"ds": "2026-01-03", "shortest_answer_length": 2**63 - 1})

    s = summarize_letter_boxed(load_game(root, "letter_boxed"))
    assert s["count"] == 3
    assert s["avg_shortest"] == 2.0        # the two unsolved boards are excluded
    assert s["score_cell"] == "2.0 words"
    assert s["word_counts"] == {2: 1, "X": 2}

    # mixed int/"X" keys must not blow up the chart's sort
    svg = word_count_pie_svg(s)
    ET.fromstring(svg)
    assert "unsolved: 2 (67%)" in svg


def test_summarize_wordle_splits_by_mode(tmp_path):
    import xml.etree.ElementTree as ET

    from stats import load_game, summarize_wordle, wordle_guesses_svg

    root = str(tmp_path)
    # same date appears in both modes; hard needs more guesses than easy
    _write(root, "wordle", "2026-01-01_easy.json", {"ds": "2026-01-01", "mode": "easy", "solved": True, "num_guesses": 3})
    _write(root, "wordle", "2026-01-01_hard.json", {"ds": "2026-01-01", "mode": "hard", "solved": True, "num_guesses": 4})
    _write(root, "wordle", "2026-01-02_hard.json", {"ds": "2026-01-02", "mode": "hard", "solved": False, "num_guesses": None})

    records = load_game(root, "wordle")
    easy = summarize_wordle(records, "easy")
    hard = summarize_wordle(records, "hard")
    assert easy["count"] == 1 and easy["avg_guesses"] == 3.0
    assert hard["count"] == 2 and hard["avg_guesses"] == 4.0  # one solved (4), one failed
    assert hard["guess_dist"] == {4: 1, "X": 1}

    svg = wordle_guesses_svg(easy, hard)
    ET.fromstring(svg)  # well-formed XML
    assert "Wordle Guess Distribution" in svg
    assert "Easy" in svg and "Hard" in svg  # grouped legend


def test_summarize_strands_and_pie(tmp_path):
    import xml.etree.ElementTree as ET

    from stats import load_game, strands_outcomes_pie_svg, summarize_strands

    root = str(tmp_path)
    _write(root, "strands", "2026-01-01.json",
           {"ds": "2026-01-01", "solved": True, "theme_words_found": 6, "theme_words_total": 6})
    _write(root, "strands", "2026-01-02.json",
           {"ds": "2026-01-02", "solved": False, "theme_words_found": 3, "theme_words_total": 6})
    _write(root, "strands", "2026-01-03.json",
           {"ds": "2026-01-03", "solved": False, "theme_words_found": 0, "theme_words_total": 5})

    s = summarize_strands(load_game(root, "strands"))
    assert s["count"] == 3
    assert s["outcome"] == {"solved": 1, "partial": 1, "missed": 1}
    assert abs(s["avg_recovery"] - (100 + 50 + 0) / 3) < 1e-9
    assert s["score_cell"] == "50% words"

    svg = strands_outcomes_pie_svg(s)
    ET.fromstring(svg)  # well-formed XML
    assert svg.count("<path") == 3  # solved / partial / missed slices


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
