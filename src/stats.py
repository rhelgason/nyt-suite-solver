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


def date_range(dates: List[str]) -> str:
    dates = sorted(d for d in dates if d)
    if not dates:
        return "—"
    return dates[0] if dates[0] == dates[-1] else f"{dates[0]} → {dates[-1]}"


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


def mermaid_bar(title: str, labels: List[str], values: List[float], y_label: str, y_max: int) -> str:
    xs = ", ".join(f'"{label}"' for label in labels)
    ys = ", ".join(str(v) for v in values)
    return (
        "```mermaid\n"
        "xychart-beta\n"
        f'    title "{title}"\n'
        f"    x-axis [{xs}]\n"
        f'    y-axis "{y_label}" 0 --> {y_max}\n'
        f"    bar [{ys}]\n"
        "```"
    )


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
        return "—"
    parts = []
    if s["avg_pct"] is not None:
        parts.append(f"avg score **{s['avg_pct']:.1f}%**")
    if s["queen_bee_rate"] is not None:
        parts.append(f"Queen Bee on **{s['queen_bee_rate']:.0f}%** of puzzles")
    return " · ".join(parts) if parts else "—"


def _letter_boxed_headline(s: dict) -> str:
    if not s["count"]:
        return "—"
    parts = []
    if s["avg_valid"] is not None:
        parts.append(f"avg **{s['avg_valid']:.1f}** valid solutions")
    if s["solved_rate"] is not None:
        parts.append(f"**{s['solved_rate']:.0f}%** solved")
    return " · ".join(parts)


def _sudoku_headline(s: dict) -> str:
    if not s["count"]:
        return "—"
    parts = [f"**{s['solved_rate']:.0f}%** solved"]
    if s["avg_ms"] is not None:
        parts.append(f"avg **{s['avg_ms']:.2f} ms**")
    return " · ".join(parts)


def rank_distribution_chart(s: dict) -> Optional[str]:
    counts = s.get("rank_counts") or {}
    ranks = [r for r in RANK_ORDER if counts.get(r)]
    if len(ranks) < 2:  # a single-bar chart adds nothing over the table
        return None
    return mermaid_bar(
        "Spelling Bee puzzles by rank achieved (lifetime)",
        [_pretty_rank(r) for r in ranks],
        [counts[r] for r in ranks],
        "Puzzles",
        max(counts[r] for r in ranks),
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

    chart = rank_distribution_chart(sb)
    if chart:
        lines.append("")
        lines.append(chart)
    return "\n".join(lines)


def update_readme(readme_text: str, section: str) -> str:
    block = f"{START_MARKER}\n{section}\n{END_MARKER}"
    if START_MARKER in readme_text and END_MARKER in readme_text:
        pre = readme_text.split(START_MARKER)[0]
        post = readme_text.split(END_MARKER, 1)[1]
        return pre + block + post
    return readme_text.rstrip() + "\n\n" + block + "\n"


def main() -> None:
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
