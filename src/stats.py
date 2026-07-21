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

# cap the chart so it stays readable as history grows
MAX_CHART_POINTS = 30

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


def render_spelling_bee(records: List[Record]) -> List[str]:
    lines = ["### Spelling Bee"]
    if not records:
        return lines + ["", "_No puzzles solved yet._"]

    by_ds = _by_date(records)
    dates = sorted(by_ds)
    pcts = [by_ds[d]["percentage"] for d in dates if isinstance(by_ds[d].get("percentage"), (int, float))]
    latest = by_ds[dates[-1]]

    lines.append("")
    lines.append(f"- Puzzles solved: **{len(dates)}** ({date_range(dates)})")
    if pcts:
        lines.append(
            f"- Score: avg **{sum(pcts) / len(pcts):.1f}%** · best **{max(pcts):.0f}%** · "
            f"latest **{latest.get('percentage', 0):.0f}%** ({latest.get('rank', 'n/a')})"
        )

    series = [(d, by_ds[d]["percentage"]) for d in dates if isinstance(by_ds[d].get("percentage"), (int, float))]
    series = series[-MAX_CHART_POINTS:]
    if series:
        # include the year in labels only when the window spans more than one
        multiyear = len({d[:4] for d, _ in series}) > 1
        labels = [d[2:] if multiyear else d[5:] for d, _ in series]
        lines.append("")
        lines.append(mermaid_bar(
            "Spelling Bee score % by date",
            labels,
            [round(p) for _, p in series],
            "Score %", 100,
        ))
    return lines


def render_letter_boxed(records: List[Record]) -> List[str]:
    lines = ["### Letter Boxed"]
    if not records:
        return lines + ["", "_No puzzles solved yet._"]

    by_ds = _by_date(records)
    dates = sorted(by_ds)
    valids = [len(as_list(by_ds[d].get("valid_answers"))) for d in dates]
    shortest = [by_ds[d]["shortest_answer_length"] for d in dates if isinstance(by_ds[d].get("shortest_answer_length"), int)]

    lines.append("")
    lines.append(f"- Puzzles solved: **{len(dates)}** ({date_range(dates)})")
    avg_valid = sum(valids) / len(valids) if valids else 0
    detail = f"- Valid solutions/day: avg **{avg_valid:.1f}** · latest **{valids[-1]}**"
    if shortest:
        detail += f" · avg shortest solution **{sum(shortest) / len(shortest):.1f}** words"
    lines.append(detail)
    return lines


def render_sudoku(records: List[Record]) -> List[str]:
    lines = ["### Sudoku"]
    if not records:
        return lines + ["", "_No puzzles solved yet._"]

    by_difficulty: Dict[str, int] = {}
    times, dates, solved = [], [], 0
    for name, data in records:
        diff = name.rsplit("_", 1)[-1].split(".")[0] if "_" in name else "unknown"
        by_difficulty[diff] = by_difficulty.get(diff, 0) + 1
        dates.append(data.get("ds"))
        if data.get("solved_puzzle"):
            solved += 1
        ms = solve_time_ms(data.get("solve_time", ""))
        if ms is not None:
            times.append(ms)

    breakdown = ", ".join(f"{k}: {v}" for k, v in sorted(by_difficulty.items()))
    lines.append("")
    lines.append(f"- Puzzles solved: **{len(records)}** ({date_range(dates)}) — {breakdown}")
    tail = f"- Solved successfully: **{solved}/{len(records)}**"
    if times:
        tail += f" · avg solve time **{sum(times) / len(times):.2f} ms**"
    lines.append(tail)
    return lines


def build_section(root: str = SOLUTIONS_ROOT) -> str:
    spelling = load_game(root, "spelling_bee")
    boxed = load_game(root, "letter_boxed")
    sudoku = load_game(root, "sudoku")

    latest = max(
        [d for _, data in spelling + boxed + sudoku for d in [data.get("ds")] if d],
        default=None,
    )

    lines = ["## Latest results", ""]
    note = f"latest puzzle {latest}" if latest else "no puzzles yet"
    lines.append(f"_Auto-generated from `solutions/` ({note})._")
    lines.append("")
    lines += render_spelling_bee(spelling)
    lines.append("")
    lines += render_letter_boxed(boxed)
    lines.append("")
    lines += render_sudoku(sudoku)
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
