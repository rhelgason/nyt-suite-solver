"""
Headless entrypoint for solving NYT puzzles without the interactive menu.

Examples:
    python src/cli.py                              # all games, today
    python src/cli.py --game spelling-bee --date 2026-07-20
    python src/cli.py --game sudoku --difficulty hard
    python src/cli.py --game spelling-bee --backfill   # every archived date

Exits non-zero if any requested puzzle failed to solve so that scheduled runs
surface breakage instead of silently skipping a day.
"""
from datetime import datetime
from typing import List, Optional

import argparse
import sys
import traceback

from menu_options import SudokuDifficultyOptions
from solvers.letter_boxed.LetterBoxedSolver import LetterBoxedSolver
from solvers.scraping import fetch_game_data
from solvers.spelling_bee.SpellingBeeSolver import SpellingBeeSolver, BASE_URL as SPELLING_BEE_BASE_URL
from solvers.sudoku.SudokuSolver import SudokuSolver

GAMES = ["letter-boxed", "spelling-bee", "sudoku"]
DATE_FORMAT = "%Y-%m-%d"

# Letter Boxed and Sudoku only expose today's puzzle; only Spelling Bee serves a
# (short) archive, so a non-today date is only meaningful there.
TODAY_ONLY_GAMES = {"letter-boxed", "sudoku"}


def today_ds() -> str:
    return datetime.today().date().strftime(DATE_FORMAT)


def valid_date(value: str) -> str:
    try:
        datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        raise argparse.ArgumentTypeError(f"date must be YYYY-MM-DD, got '{value}'")
    return value


def spelling_bee_archive_dates() -> List[str]:
    """Every date the NYT currently serves Spelling Bee data for."""
    past = fetch_game_data(SPELLING_BEE_BASE_URL)["pastPuzzles"]
    dates = set()
    for window in ("lastWeek", "thisWeek"):
        for entry in past.get(window, []):
            dates.add(entry["printDate"])
    return sorted(dates)


def _difficulties(choice: str) -> List[SudokuDifficultyOptions]:
    if choice == "all":
        return [SudokuDifficultyOptions.EASY, SudokuDifficultyOptions.MEDIUM, SudokuDifficultyOptions.HARD]
    return [SudokuDifficultyOptions[choice.upper()]]


def build_jobs(args) -> List:
    """Produce a list of (label, callable) jobs from parsed args."""
    games = GAMES if args.game == "all" else [args.game]
    jobs = []

    if args.backfill:
        if args.game not in ("spelling-bee", "all"):
            raise SystemExit("--backfill is only supported for spelling-bee")
        for ds in spelling_bee_archive_dates():
            jobs.append((f"spelling-bee {ds}", lambda ds=ds: SpellingBeeSolver(ds).solve()))
        return jobs

    ds = args.date or today_ds()
    is_today = ds == today_ds()

    for game in games:
        if game in TODAY_ONLY_GAMES and not is_today:
            print(f"! skipping {game} for {ds}: only today's puzzle is available")
            continue
        if game == "letter-boxed":
            jobs.append((f"letter-boxed {ds}", lambda: LetterBoxedSolver().solve()))
        elif game == "spelling-bee":
            jobs.append((f"spelling-bee {ds}", lambda ds=ds: SpellingBeeSolver(ds).solve()))
        elif game == "sudoku":
            for diff in _difficulties(args.difficulty):
                label = f"sudoku {diff.value.lower()} {ds}"
                jobs.append((label, lambda diff=diff: SudokuSolver(diff).solve()))

    return jobs


def run(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Solve NYT puzzles headlessly.")
    parser.add_argument("--game", choices=GAMES + ["all"], default="all")
    parser.add_argument("--date", type=valid_date, default=None,
                        help="YYYY-MM-DD (Spelling Bee only; defaults to today)")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard", "all"], default="all",
                        help="Sudoku difficulty (default: all)")
    parser.add_argument("--backfill", action="store_true",
                        help="solve every archived Spelling Bee date")
    args = parser.parse_args(argv)

    jobs = build_jobs(args)
    if not jobs:
        print("Nothing to solve.")
        return 0

    results = []
    for label, job in jobs:
        try:
            job()
            results.append((label, True, None))
        except Exception as e:  # noqa: BLE001 - keep going so other games still run
            traceback.print_exc()
            results.append((label, False, str(e)))

    failures = [r for r in results if not r[1]]
    print("\n=== Summary ===")
    for label, ok, err in results:
        print(f"  {'OK ' if ok else 'FAIL'}  {label}" + (f"  ({err})" if err else ""))
    print(f"{len(results) - len(failures)}/{len(results)} solved")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
