"""
Regenerate the auto-updated stats section of the README from the committed
solution JSON files. Run by the daily workflow after solving (and via
`make stats`), so the repo's front page always reflects the latest history
without any hosted service.
"""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import ast
import bisect
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


def summarize_wordle(records: List[Record]) -> dict:
    by_ds = _by_date(records)
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
        "p90_ms": _percentile(_runtimes_ms(records), 90),
        "score_cell": f"{avg:.1f} guesses" if avg is not None else "n/a",
    }


# game order and colors used for the cumulative chart's legend/lines
CUMULATIVE_GAMES = [
    ("spelling_bee", "Spelling Bee", "#eab308"),
    ("letter_boxed", "Letter Boxed", "#2563eb"),
    ("sudoku", "Sudoku", "#dc2626"),
    ("wordle", "Wordle", "#7c3aed"),
]

ASSETS_DIR = os.path.join(REPO_ROOT, "stats")
CUMULATIVE_SVG_REL = "stats/cumulative_solves.svg"
SCORES_SVG_REL = "stats/spelling_bee_scores.svg"
WORDS_SVG_REL = "stats/letter_boxed_words.svg"
WORDLE_SVG_REL = "stats/wordle_guesses.svg"


def _parse_date(value: str) -> date:
    return date(int(value[:4]), int(value[5:7]), int(value[8:10]))


def _add_months(base: date, months: int) -> date:
    total = base.month - 1 + months
    return date(base.year + total // 12, total % 12 + 1, 1)


def time_axis_ticks(dmin: date, dmax: date, target: int = 7) -> List[Tuple[float, str]]:
    """Choose readable, calendar-aligned x-axis ticks that scale with the span:
    days for a short window, then weeks, months, and finally years. Tick count
    stays near `target` regardless of how much history accumulates."""
    span = (dmax - dmin).days
    ticks: List[Tuple[float, str]] = []
    if span <= 0:
        return [(dmin.toordinal(), dmin.strftime("%m-%d"))]

    if span <= 21:  # daily
        stride = max(1, _ceil_div(span, target))
        cur = dmin
        while cur <= dmax:
            ticks.append((cur.toordinal(), cur.strftime("%m-%d")))
            cur += timedelta(days=stride)
    elif span <= 120:  # weekly
        stride = max(1, _ceil_div(span, 7 * target)) * 7
        cur = dmin
        while cur <= dmax:
            ticks.append((cur.toordinal(), cur.strftime("%m-%d")))
            cur += timedelta(days=stride)
    elif span <= 365 * 3:  # monthly
        stride = max(1, _ceil_div(span, 30 * target))
        cur = date(dmin.year, dmin.month, 1)
        while cur <= dmax:
            if cur >= dmin:
                ticks.append((cur.toordinal(), cur.strftime("%b %y")))
            cur = _add_months(cur, stride)
    else:  # yearly
        stride = max(1, _ceil_div(span, 365 * target))
        cur = date(dmin.year, 1, 1)
        while cur <= dmax:
            if cur >= dmin:
                ticks.append((cur.toordinal(), cur.strftime("%Y")))
            cur = date(cur.year + stride, 1, 1)

    if len(ticks) < 2:
        ticks = [(dmin.toordinal(), dmin.strftime("%m-%d")), (dmax.toordinal(), dmax.strftime("%m-%d"))]
    return ticks


def cumulative_solves_svg(games: Dict[str, List[Record]]) -> Optional[str]:
    per_game = {
        key: sorted(data.get("ds") for _, data in games.get(key, []) if data.get("ds"))
        for key, _, _ in CUMULATIVE_GAMES
    }
    all_dates = sorted({d for dates in per_game.values() for d in dates})
    if len(all_dates) < 2:  # need at least two points to draw a line
        return None

    x_values = [_parse_date(d).toordinal() for d in all_dates]
    ticks = time_axis_ticks(_parse_date(all_dates[0]), _parse_date(all_dates[-1]))
    series = [
        (name, color, [bisect.bisect_right(per_game[key], d) for d in all_dates])
        for key, name, color in CUMULATIVE_GAMES
    ]
    return svg_charts.line_chart("Cumulative Puzzles Solved", x_values, series, "Puzzles solved", ticks)


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


def wordle_guesses_svg(s: dict) -> Optional[str]:
    dist = s.get("guess_dist") or {}
    if not dist:
        return None
    labels = [str(i) for i in range(1, 7)]
    values = [dist.get(i, 0) for i in range(1, 7)]
    if dist.get("X"):  # failed puzzles
        labels.append("X")
        values.append(dist["X"])
    return svg_charts.bar_chart("Wordle Guess Distribution", labels, values, "#7c3aed", "Puzzles")


GAMES = ("spelling_bee", "letter_boxed", "sudoku", "wordle")


def build_section(root: str = SOLUTIONS_ROOT) -> str:
    games = {g: load_game(root, g) for g in GAMES}
    all_dates = [data.get("ds") for recs in games.values() for _, data in recs if data.get("ds")]
    latest = max(all_dates) if all_dates else None

    sb = summarize_spelling_bee(games["spelling_bee"])
    lb = summarize_letter_boxed(games["letter_boxed"])
    sk = summarize_sudoku(games["sudoku"])
    wd = summarize_wordle(games["wordle"])
    rows = [("Spelling Bee", sb), ("Letter Boxed", lb), ("Sudoku", sk), ("Wordle", wd)]
    total = sum(s["count"] for _, s in rows)
    played = sum(1 for _, s in rows if s["count"] > 0)

    lines = ["## Lifetime results", ""]
    if total == 0:
        return "\n".join(lines + ["_No puzzles solved yet._"])

    lines.append(f"_Auto-generated from `solutions/` · **{total}** puzzles solved across {played} games (through {latest})._")
    lines.append("")
    lines.append("| Game | Puzzles | Avg score | p90 runtime |")
    lines.append("| --- | ---: | ---: | ---: |")
    for name, s in rows:
        lines.append(f"| {name} | {s['count']} | {s['score_cell']} | {_format_runtime(s['p90_ms'])} |")

    if cumulative_solves_svg(games) is not None:
        lines.append("")
        lines.append(f'<p align="center"><img src="{CUMULATIVE_SVG_REL}" alt="Cumulative Puzzles Solved" width="720"></p>')
    return "\n".join(lines)


def write_assets(root: str = SOLUTIONS_ROOT, assets_dir: str = ASSETS_DIR) -> None:
    """Write the committed chart images referenced by the README."""
    games = {g: load_game(root, g) for g in GAMES}
    assets = {
        "cumulative_solves.svg": cumulative_solves_svg(games),
        "spelling_bee_scores.svg": score_pie_svg(summarize_spelling_bee(games["spelling_bee"])),
        "letter_boxed_words.svg": word_count_pie_svg(summarize_letter_boxed(games["letter_boxed"])),
        "wordle_guesses.svg": wordle_guesses_svg(summarize_wordle(games["wordle"])),
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
