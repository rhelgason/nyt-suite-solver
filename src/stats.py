"""
Regenerate the auto-updated stats section of the README from the committed
solution JSON files. Run by the daily workflow after solving (and via
`make stats`), so the repo's front page always reflects the latest history
without any hosted service.
"""
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


def _mermaid_chart(title: str, labels: List[str], y_label: str, y_max: int, plots: List[str]) -> str:
    xs = ", ".join(f'"{label}"' for label in labels)
    body = "".join(f"    {plot}\n" for plot in plots)
    return (
        "```mermaid\n"
        "xychart-beta\n"
        f'    title "{title}"\n'
        f"    x-axis [{xs}]\n"
        f'    y-axis "{y_label}" 0 --> {y_max}\n'
        f"{body}```"
    )


def mermaid_bar(title: str, labels: List[str], values: List[float], y_label: str, y_max: int) -> str:
    return _mermaid_chart(title, labels, y_label, y_max, [f"bar [{', '.join(str(v) for v in values)}]"])




# canonical Spelling Bee ranks, best to worst
RANK_ORDER = [
    "QUEEN_BEE", "GENIUS", "AMAZING", "GREAT", "NICE",
    "SOLID", "GOOD", "MOVING_UP", "GOOD_START", "BEGINNER",
]


def _pretty_rank(name: str) -> str:
    return name.replace("_", " ").title()


def summarize_spelling_bee(records: List[Record]) -> dict:
    by_ds = _by_date(records)
    dates = sorted(by_ds)
    pcts = [by_ds[d]["percentage"] for d in dates if isinstance(by_ds[d].get("percentage"), (int, float))]
    ranks = [by_ds[d]["rank"] for d in dates if by_ds[d].get("rank")]
    rank_counts = {r: ranks.count(r) for r in RANK_ORDER if r in ranks}
    return {
        "count": len(dates),
        "percentages": pcts,
        "avg_pct": sum(pcts) / len(pcts) if pcts else None,
        "best_pct": max(pcts) if pcts else None,
        "queen_bee_rate": ranks.count("QUEEN_BEE") / len(ranks) * 100 if ranks else None,
        "rank_counts": rank_counts,
        "total_pangrams": sum(len(as_list(by_ds[d].get("pangrams"))) for d in dates),
    }


def summarize_letter_boxed(records: List[Record]) -> dict:
    by_ds = _by_date(records)
    dates = sorted(by_ds)
    valids = [len(as_list(by_ds[d].get("valid_answers"))) for d in dates]
    shortest = [by_ds[d]["shortest_answer_length"] for d in dates if isinstance(by_ds[d].get("shortest_answer_length"), int)]
    return {
        "count": len(dates),
        "avg_valid": sum(valids) / len(valids) if valids else None,
        "avg_shortest": sum(shortest) / len(shortest) if shortest else None,
        "solved_rate": sum(1 for v in valids if v > 0) / len(valids) * 100 if valids else None,
    }


def summarize_sudoku(records: List[Record]) -> dict:
    by_difficulty: Dict[str, int] = {}
    times, solved = [], 0
    for name, data in records:
        diff = name.rsplit("_", 1)[-1].split(".")[0] if "_" in name else "unknown"
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1
        if data.get("solved_puzzle"):
            solved += 1
        ms = solve_time_ms(data.get("solve_time", ""))
        if ms is not None:
            times.append(ms)
    return {
        "count": len(records),
        "by_difficulty": by_difficulty,
        "solved_rate": solved / len(records) * 100 if records else None,
        "avg_ms": sum(times) / len(times) if times else None,
    }


def _spelling_bee_headline(s: dict) -> str:
    if not s["count"]:
        return "no puzzles yet"
    parts = []
    if s["avg_pct"] is not None:
        parts.append(f"avg score **{s['avg_pct']:.1f}%**")
    if s["queen_bee_rate"] is not None:
        parts.append(f"Queen Bee on **{s['queen_bee_rate']:.0f}%** of puzzles")
    return " · ".join(parts) if parts else "no puzzles yet"


def _letter_boxed_headline(s: dict) -> str:
    if not s["count"]:
        return "no puzzles yet"
    parts = []
    if s["avg_valid"] is not None:
        parts.append(f"avg **{s['avg_valid']:.1f}** valid solutions")
    if s["solved_rate"] is not None:
        parts.append(f"**{s['solved_rate']:.0f}%** solved")
    return " · ".join(parts)


def _sudoku_headline(s: dict) -> str:
    if not s["count"]:
        return "no puzzles yet"
    parts = [f"**{s['solved_rate']:.0f}%** solved"]
    if s["avg_ms"] is not None:
        parts.append(f"avg **{s['avg_ms']:.2f} ms**")
    return " · ".join(parts)


# game order and colors used for the cumulative chart's legend/lines
CUMULATIVE_GAMES = [
    ("spelling_bee", "Spelling Bee", "#eab308"),
    ("letter_boxed", "Letter Boxed", "#2563eb"),
    ("sudoku", "Sudoku", "#dc2626"),
]

ASSETS_DIR = os.path.join(REPO_ROOT, "stats")
CUMULATIVE_SVG_REL = "stats/cumulative_solves.svg"


def cumulative_solves_svg(games: Dict[str, List[Record]]) -> Optional[str]:
    per_game = {
        key: sorted(data.get("ds") for _, data in games[key] if data.get("ds"))
        for key, _, _ in CUMULATIVE_GAMES
    }
    all_dates = sorted({d for dates in per_game.values() for d in dates})
    if len(all_dates) < 2:  # need at least two points to draw a line
        return None

    multiyear = len({d[:4] for d in all_dates}) > 1
    labels = [d[2:] if multiyear else d[5:] for d in all_dates]
    series = [
        (name, color, [bisect.bisect_right(per_game[key], d) for d in all_dates])
        for key, name, color in CUMULATIVE_GAMES
    ]
    return svg_charts.line_chart("Cumulative puzzles solved", labels, series, "Puzzles solved")


SCORE_BUCKETS = ["<80", "80-89", "90-94", "95-99", "100"]


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


def score_histogram_chart(s: dict) -> Optional[str]:
    pcts = s.get("percentages") or []
    if len(pcts) < 2:
        return None
    counts = [0] * len(SCORE_BUCKETS)
    for pct in pcts:
        counts[_score_bucket(pct)] += 1
    # trim leading empty buckets so the chart focuses on the range in use
    first = next((i for i, c in enumerate(counts) if c > 0), 0)
    labels, counts = SCORE_BUCKETS[first:], counts[first:]
    return mermaid_bar(
        "Spelling Bee score distribution (lifetime)",
        labels,
        counts,
        "Puzzles",
        max(counts),
    )


def build_section(root: str = SOLUTIONS_ROOT) -> str:
    games = {g: load_game(root, g) for g in ("spelling_bee", "letter_boxed", "sudoku")}
    all_dates = [data.get("ds") for recs in games.values() for _, data in recs if data.get("ds")]
    latest = max(all_dates) if all_dates else None

    sb = summarize_spelling_bee(games["spelling_bee"])
    lb = summarize_letter_boxed(games["letter_boxed"])
    sk = summarize_sudoku(games["sudoku"])
    total = sb["count"] + lb["count"] + sk["count"]

    lines = ["## Lifetime results", ""]
    if total == 0:
        return "\n".join(lines + ["_No puzzles solved yet._"])

    lines.append(f"_Auto-generated from `solutions/` · **{total}** puzzles solved across 3 games (through {latest})._")
    lines.append("")
    lines.append("| Game | Puzzles | Lifetime performance |")
    lines.append("| --- | ---: | --- |")
    lines.append(f"| Spelling Bee | {sb['count']} | {_spelling_bee_headline(sb)} |")
    lines.append(f"| Letter Boxed | {lb['count']} | {_letter_boxed_headline(lb)} |")
    lines.append(f"| Sudoku | {sk['count']} | {_sudoku_headline(sk)} |")

    if cumulative_solves_svg(games) is not None:
        lines.append("")
        lines.append(f"![Cumulative puzzles solved by game]({CUMULATIVE_SVG_REL})")

    histogram = score_histogram_chart(sb)
    if histogram:
        lines.append("")
        lines.append(histogram)
    return "\n".join(lines)


def write_assets(root: str = SOLUTIONS_ROOT, assets_dir: str = ASSETS_DIR) -> None:
    """Write the committed chart image(s) referenced by the README section."""
    games = {g: load_game(root, g) for g in ("spelling_bee", "letter_boxed", "sudoku")}
    svg = cumulative_solves_svg(games)
    if svg is None:
        return
    os.makedirs(assets_dir, exist_ok=True)
    with open(os.path.join(assets_dir, "cumulative_solves.svg"), "w", encoding="utf-8") as f:
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
