"""
Regenerate the auto-updated stats section of the README from the committed
solution JSON files. Run by the daily workflow after solving (and via
`make stats`), so the repo's front page always reflects the latest history
without any hosted service.
"""
from typing import Dict, List, Optional, Tuple

import ast
import glob
import json
import os

import svg_charts

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOLUTIONS_ROOT = os.path.join(REPO_ROOT, "solutions")
README_PATH = os.path.join(REPO_ROOT, "README.md")

START_MARKER = "<!-- STATS:START -->"
END_MARKER = "<!-- STATS:END -->"

Record = Tuple[str, dict]  # (filename, parsed json)


def load_game(root: str, game: str) -> List[Record]:
    records = []
    for path in sorted(glob.glob(os.path.join(root, game, "*.json"))):
        try:
            with open(path) as f:
                records.append((os.path.basename(path), json.load(f)))
        except (OSError, json.JSONDecodeError):
            continue
    return records


def solve_time_ms(value: str) -> Optional[float]:
    try:
        hours, minutes, seconds = value.split(":")
        return ((int(hours) * 60 + int(minutes)) * 60 + float(seconds)) * 1000
    except (ValueError, AttributeError):
        return None


def _by_date(records: List[Record]) -> Dict[str, dict]:
    return {data["ds"]: data for _, data in records if data.get("ds")}


def as_list(value) -> list:
    """Coerce a field to a list, tolerating the legacy format where some fields
    were stored as a stringified Python list."""
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, list) else []
        except (ValueError, SyntaxError):
            return []
    return []

def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def _percentile(values: List[float], p: int) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, _ceil_div(p * len(ordered), 100))  # nearest-rank method
    return ordered[min(rank, len(ordered)) - 1]


def _runtimes_ms(records: List[Record]) -> List[float]:
    times = [solve_time_ms(data.get("solve_time", "")) for _, data in records]
    return [t for t in times if t is not None]


def _format_runtime(ms: Optional[float]) -> str:
    if ms is None:
        return "n/a"
    if ms >= 1000:
        return f"{ms / 1000:.2f} s"
    if ms >= 1:
        return f"{ms:.0f} ms"
    return f"{ms:.2f} ms"


def summarize_spelling_bee(records: List[Record]) -> dict:
    by_ds = _by_date(records)
    dates = sorted(by_ds)
    pcts = [by_ds[d]["percentage"] for d in dates if isinstance(by_ds[d].get("percentage"), (int, float))]
    return {
        "count": len(dates),
        "percentages": pcts,
        "avg_pct": sum(pcts) / len(pcts) if pcts else None,
        "p90_ms": _percentile(_runtimes_ms(records), 90),
        "score_cell": f"{sum(pcts) / len(pcts):.1f}%" if pcts else "n/a",
    }


def summarize_letter_boxed(records: List[Record]) -> dict:
    by_ds = _by_date(records)
    dates = sorted(by_ds)
    shortest = [by_ds[d]["shortest_answer_length"] for d in dates if isinstance(by_ds[d].get("shortest_answer_length"), int)]
    word_counts: Dict[int, int] = {}
    for n in shortest:
        word_counts[n] = word_counts.get(n, 0) + 1
    avg_shortest = sum(shortest) / len(shortest) if shortest else None
    return {
        "count": len(dates),
        "avg_shortest": avg_shortest,
        "word_counts": word_counts,
        "p90_ms": _percentile(_runtimes_ms(records), 90),
        "score_cell": f"{avg_shortest:.1f} words" if avg_shortest is not None else "n/a",
    }


def summarize_sudoku(records: List[Record]) -> dict:
    solved = sum(1 for _, data in records if data.get("solved_puzzle"))
    solved_rate = solved / len(records) * 100 if records else None
    return {
        "count": len(records),
        "solved_rate": solved_rate,
        "p90_ms": _percentile(_runtimes_ms(records), 90),
        "score_cell": f"{solved_rate:.0f}%" if solved_rate is not None else "n/a",
    }


def summarize_wordle(records: List[Record], mode: str) -> dict:
    """Summarize one Wordle mode ('easy' or 'hard'). Records of both modes share
    a date, so filter by the stored mode rather than keying on the date alone."""
    mode_records = [(name, data) for name, data in records if data.get("mode") == mode]
    by_ds = _by_date(mode_records)
    dates = sorted(by_ds)
    guesses = [by_ds[d]["num_guesses"] for d in dates
               if by_ds[d].get("solved") and isinstance(by_ds[d].get("num_guesses"), int)]
    dist: Dict[object, int] = {}
    for d in dates:
        rec = by_ds[d]
        if rec.get("solved") and isinstance(rec.get("num_guesses"), int):
            dist[rec["num_guesses"]] = dist.get(rec["num_guesses"], 0) + 1
        else:
            dist["X"] = dist.get("X", 0) + 1
    avg = sum(guesses) / len(guesses) if guesses else None
    return {
        "count": len(dates),
        "avg_guesses": avg,
        "guess_dist": dist,
        "p90_ms": _percentile(_runtimes_ms(mode_records), 90),
        "score_cell": f"{avg:.1f} guesses" if avg is not None else "n/a",
    }


def summarize_strands(records: List[Record]) -> dict:
    by_ds = _by_date(records)
    dates = sorted(by_ds)
    solved = partial = missed = 0
    recovery = []
    for d in dates:
        rec = by_ds[d]
        total = rec.get("theme_words_total") or 0
        found = rec.get("theme_words_found") or 0
        if total:
            recovery.append(found / total * 100)
        if rec.get("solved"):
            solved += 1
        elif found > 0:
            partial += 1
        else:
            missed += 1
    avg_recovery = sum(recovery) / len(recovery) if recovery else None
    return {
        "count": len(dates),
        "outcome": {"solved": solved, "partial": partial, "missed": missed},
        "avg_recovery": avg_recovery,
        "p90_ms": _percentile(_runtimes_ms(records), 90),
        "score_cell": f"{avg_recovery:.0f}% words" if avg_recovery is not None else "n/a",
    }


def summarize_connections(records: List[Record]) -> dict:
    by_ds = _by_date(records)
    dates = sorted(by_ds)
    solved = 0
    groups_dist = {n: 0 for n in range(5)}  # how many groups found, 0..4
    for d in dates:
        rec = by_ds[d]
        found = rec.get("groups_found")
        if not isinstance(found, int):
            found = 4 if rec.get("solved") else 0
        groups_dist[max(0, min(4, found))] += 1
        if rec.get("solved"):
            solved += 1
    solve_rate = solved / len(dates) * 100 if dates else None
    return {
        "count": len(dates),
        "solve_rate": solve_rate,
        "groups_dist": groups_dist,
        "p90_ms": _percentile(_runtimes_ms(records), 90),
        "score_cell": f"{solve_rate:.0f}%" if solve_rate is not None else "n/a",
    }


def summarize_crossword(records: List[Record]) -> dict:
    by_ds = _by_date(records)
    dates = sorted(by_ds)
    accuracies, solved = [], 0
    for d in dates:
        rec = by_ds[d]
        total = rec.get("cells_total") or 0
        correct = rec.get("cells_correct") or 0
        if total:
            accuracies.append(correct / total * 100)
        if rec.get("solved"):
            solved += 1
    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else None
    return {
        "count": len(dates),
        "avg_accuracy": avg_accuracy,
        "outcome": {"solved": solved, "failed": len(dates) - solved},
        "p90_ms": _percentile(_runtimes_ms(records), 90),
        "score_cell": f"{avg_accuracy:.0f}% cells" if avg_accuracy is not None else "n/a",
    }


ASSETS_DIR = os.path.join(REPO_ROOT, "stats")
SCORES_SVG_REL = "stats/spelling_bee_scores.svg"
WORDS_SVG_REL = "stats/letter_boxed_words.svg"
WORDLE_SVG_REL = "stats/wordle_guesses.svg"
STRANDS_SVG_REL = "stats/strands_outcomes.svg"
CONNECTIONS_SVG_REL = "stats/connections_groups.svg"
CROSSWORD_SVG_REL = "stats/crossword_passfail.svg"


# score buckets for the pie, with a red-to-green (worse-to-better) palette
SCORE_BUCKETS = [
    ("<80", "#dc2626"),
    ("80-89", "#f59e0b"),
    ("90-94", "#eab308"),
    ("95-99", "#84cc16"),
    ("100", "#16a34a"),
]


def _score_bucket(pct: float) -> int:
    if pct >= 100:
        return 4
    if pct >= 95:
        return 3
    if pct >= 90:
        return 2
    if pct >= 80:
        return 1
    return 0


def score_pie_svg(s: dict) -> Optional[str]:
    pcts = s.get("percentages") or []
    if not pcts:
        return None
    counts = [0] * len(SCORE_BUCKETS)
    for pct in pcts:
        counts[_score_bucket(pct)] += 1
    slices = [(label, counts[i], color) for i, (label, color) in enumerate(SCORE_BUCKETS) if counts[i] > 0]
    return svg_charts.pie_chart("Spelling Bee Score Distribution", slices)


# colors for the Letter Boxed words-per-solution pie (fewer words is better)
WORD_COUNT_COLORS = {1: "#16a34a", 2: "#2563eb", 3: "#f59e0b"}


def word_count_pie_svg(s: dict) -> Optional[str]:
    counts = s.get("word_counts") or {}
    if not counts:
        return None
    slices = []
    for n in sorted(counts):
        label = f"{n} word" if n == 1 else f"{n} words"
        slices.append((label, counts[n], WORD_COUNT_COLORS.get(n, "#6b7280")))
    return svg_charts.pie_chart("Letter Boxed Words per Solution", slices)


def wordle_guesses_svg(easy: dict, hard: dict) -> Optional[str]:
    easy_dist = easy.get("guess_dist") or {}
    hard_dist = hard.get("guess_dist") or {}
    if not easy_dist and not hard_dist:
        return None
    has_fail = bool(easy_dist.get("X") or hard_dist.get("X"))
    labels = [str(i) for i in range(1, 7)] + (["X"] if has_fail else [])

    def values(dist: Dict[object, int]) -> List[int]:
        vals = [dist.get(i, 0) for i in range(1, 7)]
        if has_fail:
            vals.append(dist.get("X", 0))
        return vals

    series = [("Easy", "#a78bfa", values(easy_dist)), ("Hard", "#7c3aed", values(hard_dist))]
    return svg_charts.grouped_bar_chart("Wordle Guess Distribution", labels, series, "Puzzles")


def strands_outcomes_pie_svg(s: dict) -> Optional[str]:
    outcome = s.get("outcome") or {}
    slices = [
        ("All theme words", outcome.get("solved", 0), "#16a34a"),
        ("Some theme words", outcome.get("partial", 0), "#f59e0b"),
        ("None", outcome.get("missed", 0), "#dc2626"),
    ]
    slices = [(label, value, color) for label, value, color in slices if value > 0]
    if not slices:
        return None
    return svg_charts.pie_chart("Strands Outcomes", slices)


# red (0 groups) through green (all 4) for the Connections groups-found pie
GROUPS_FOUND_COLORS = {0: "#dc2626", 1: "#f59e0b", 2: "#eab308", 3: "#84cc16", 4: "#16a34a"}


def connections_groups_pie_svg(s: dict) -> Optional[str]:
    dist = s.get("groups_dist") or {}
    slices = []
    for n in range(5):
        count = dist.get(n, 0)
        if count > 0:
            label = "All 4 groups" if n == 4 else f"{n} group" + ("" if n == 1 else "s")
            slices.append((label, count, GROUPS_FOUND_COLORS[n]))
    if not slices:
        return None
    return svg_charts.pie_chart("Connections Groups Found", slices)


def crossword_passfail_pie_svg(s: dict) -> Optional[str]:
    outcome = s.get("outcome") or {}
    slices = [
        ("Solved", outcome.get("solved", 0), "#16a34a"),
        ("Failed", outcome.get("failed", 0), "#dc2626"),
    ]
    slices = [(label, value, color) for label, value, color in slices if value > 0]
    if not slices:
        return None
    return svg_charts.pie_chart("Mini Crossword Pass / Fail", slices)


GAMES = ("spelling_bee", "letter_boxed", "sudoku", "wordle", "strands", "connections", "crossword")


def build_section(root: str = SOLUTIONS_ROOT) -> str:
    games = {g: load_game(root, g) for g in GAMES}
    all_dates = [data.get("ds") for recs in games.values() for _, data in recs if data.get("ds")]
    latest = max(all_dates) if all_dates else None

    sb = summarize_spelling_bee(games["spelling_bee"])
    lb = summarize_letter_boxed(games["letter_boxed"])
    sk = summarize_sudoku(games["sudoku"])
    wd_easy = summarize_wordle(games["wordle"], "easy")
    wd_hard = summarize_wordle(games["wordle"], "hard")
    st = summarize_strands(games["strands"])
    cn = summarize_connections(games["connections"])
    cw = summarize_crossword(games["crossword"])
    rows = [
        ("Spelling Bee", sb),
        ("Letter Boxed", lb),
        ("Sudoku", sk),
        ("Wordle (easy)", wd_easy),
        ("Wordle (hard)", wd_hard),
        ("Strands", st),
        ("Connections", cn),
        ("Mini Crossword", cw),
    ]
    total = sum(s["count"] for _, s in rows)
    played = sum(1 for g in GAMES if games[g])

    lines = ["## Lifetime results", ""]
    if total == 0:
        return "\n".join(lines + ["_No puzzles solved yet._"])

    lines.append(f"_Auto-generated from `solutions/` · **{total}** puzzles solved across {played} games (through {latest})._")
    lines.append("")
    # centered HTML table (a markdown table cannot be centered on GitHub)
    lines.append('<div align="center">')
    lines.append("<table>")
    lines.append("<tr><th>Game</th><th>Puzzles</th><th>Avg score</th><th>p90 runtime</th></tr>")
    for name, s in rows:
        lines.append(f"<tr><td>{name}</td><td>{s['count']}</td>"
                     f"<td>{s['score_cell']}</td><td>{_format_runtime(s['p90_ms'])}</td></tr>")
    lines.append("</table>")
    lines.append("</div>")
    return "\n".join(lines)


def write_assets(root: str = SOLUTIONS_ROOT, assets_dir: str = ASSETS_DIR) -> None:
    """Write the committed chart images referenced by the README."""
    games = {g: load_game(root, g) for g in GAMES}
    assets = {
        "spelling_bee_scores.svg": score_pie_svg(summarize_spelling_bee(games["spelling_bee"])),
        "letter_boxed_words.svg": word_count_pie_svg(summarize_letter_boxed(games["letter_boxed"])),
        "wordle_guesses.svg": wordle_guesses_svg(
            summarize_wordle(games["wordle"], "easy"), summarize_wordle(games["wordle"], "hard")
        ),
        "strands_outcomes.svg": strands_outcomes_pie_svg(summarize_strands(games["strands"])),
        "connections_groups.svg": connections_groups_pie_svg(summarize_connections(games["connections"])),
        "crossword_passfail.svg": crossword_passfail_pie_svg(summarize_crossword(games["crossword"])),
    }
    os.makedirs(assets_dir, exist_ok=True)
    for name, svg in assets.items():
        if svg is not None:
            with open(os.path.join(assets_dir, name), "w", encoding="utf-8") as f:
                f.write(svg)


def update_readme(readme_text: str, section: str) -> str:
    block = f"{START_MARKER}\n{section}\n{END_MARKER}"
    if START_MARKER in readme_text and END_MARKER in readme_text:
        pre = readme_text.split(START_MARKER)[0]
        post = readme_text.split(END_MARKER, 1)[1]
        return pre + block + post
    return readme_text.rstrip() + "\n\n" + block + "\n"


def main() -> None:
    write_assets()
    section = build_section()
    with open(README_PATH) as f:
        text = f.read()
    updated = update_readme(text, section)
    if updated != text:
        with open(README_PATH, "w") as f:
            f.write(updated)
        print("README stats updated.")
    else:
        print("README stats unchanged.")


if __name__ == "__main__":
    main()
