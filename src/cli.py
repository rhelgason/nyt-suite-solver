"""
Headless entrypoint for solving NYT puzzles without the interactive menu.

Examples:
    python src/cli.py                              # all games, today
    python src/cli.py --game spelling-bee --date 2026-07-20
    python src/cli.py --game sudoku --difficulty hard
    python src/cli.py --game spelling-bee --backfill        # every archived date
    python src/cli.py --game wordle --backfill --delay 0.5  # full history, politely
    python src/cli.py --game strands --backfill --since 2026-01-01

Exits non-zero if any requested puzzle failed to solve so that scheduled runs
surface breakage instead of silently skipping a day.
"""
from datetime import datetime, timedelta
from typing import List, Optional

import argparse
import os
import sys
import time
import traceback

from menu_options import SudokuDifficultyOptions
from solvers.letter_boxed.LetterBoxedSolver import LetterBoxedSolver
from solvers.scraping import fetch_game_data
from solvers.spelling_bee.SpellingBeeSolver import SpellingBeeSolver, BASE_URL as SPELLING_BEE_BASE_URL
from solvers.strands.StrandsSolver import StrandsSolver
from solvers.sudoku.SudokuSolver import SudokuSolver
from solvers.wordle.WordleSolver import WordleSolver

GAMES = ["letter-boxed", "spelling-bee", "sudoku", "wordle", "strands"]
DATE_FORMAT = "%Y-%m-%d"

# Letter Boxed and Sudoku only expose today's puzzle; Spelling Bee serves a short
# archive, and Wordle and Strands serve their full history, so a non-today date
# works for those.
TODAY_ONLY_GAMES = {"letter-boxed", "sudoku"}

# Games with a full date-addressable history and the earliest date NYT serves.
# Spelling Bee only exposes a rolling ~1-week archive (handled separately).
HISTORY_EPOCHS = {
    "wordle": "2021-06-19",   # Wordle #1
    "strands": "2024-03-04",  # Strands #1
}
BACKFILL_GAMES = ("spelling-bee", "wordle", "strands")


def today_ds() -> str:
    return datetime.today().date().strftime(DATE_FORMAT)


def date_range(start: str, end: str) -> List[str]:
    """Every YYYY-MM-DD from start to end inclusive, oldest first."""
    d = datetime.strptime(start, DATE_FORMAT).date()
    last = datetime.strptime(end, DATE_FORMAT).date()
    out = []
    while d <= last:
        out.append(d.strftime(DATE_FORMAT))
        d += timedelta(days=1)
    return out


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


def _already_solved(game: str, ds: str) -> bool:
    """True if a solution file for this game/date already exists (so backfill is
    resumable and does not re-solve work already committed)."""
    if game == "wordle":
        paths = [f"{WordleSolver.OUTPUT_DIRECTORY_PATH}/{ds}_easy.json",
                 f"{WordleSolver.OUTPUT_DIRECTORY_PATH}/{ds}_hard.json"]
        return all(os.path.exists(p) for p in paths)
    if game == "strands":
        return os.path.exists(f"{StrandsSolver.OUTPUT_DIRECTORY_PATH}/{ds}.json")
    if game == "spelling-bee":
        return os.path.exists(f"{SpellingBeeSolver.OUTPUT_DIRECTORY_PATH}/{ds}.json")
    return False


def backfill_jobs(game: str, since: Optional[str], force: bool) -> List:
    """Every solvable historical date for a game, oldest first, skipping dates
    already on disk unless force is set."""
    if game == "spelling-bee":
        dates = spelling_bee_archive_dates()
    else:
        start = max(since, HISTORY_EPOCHS[game]) if since else HISTORY_EPOCHS[game]
        dates = date_range(start, today_ds())

    jobs = []
    for ds in dates:
        if not force and _already_solved(game, ds):
            continue
        if game == "spelling-bee":
            jobs.append((f"spelling-bee {ds}", lambda ds=ds: SpellingBeeSolver(ds).solve()))
        elif game == "wordle":
            for hard in (False, True):
                mode = "hard" if hard else "easy"
                jobs.append((f"wordle {mode} {ds}", lambda ds=ds, hard=hard: WordleSolver(ds, hard=hard).solve()))
        elif game == "strands":
            jobs.append((f"strands {ds}", lambda ds=ds: StrandsSolver(ds).solve()))
    return jobs


def build_jobs(args) -> List:
    """Produce a list of (label, callable) jobs from parsed args."""
    games = GAMES if args.game == "all" else [args.game]
    jobs = []

    if args.backfill:
        targets = [g for g in BACKFILL_GAMES if args.game in (g, "all")]
        if not targets:
            raise SystemExit(f"--backfill is only supported for {', '.join(BACKFILL_GAMES)}")
        for game in targets:
            jobs.extend(backfill_jobs(game, args.since, args.force))
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
        elif game == "wordle":
            for hard in (False, True):
                mode = "hard" if hard else "easy"
                jobs.append((f"wordle {mode} {ds}", lambda ds=ds, hard=hard: WordleSolver(ds, hard=hard).solve()))
        elif game == "strands":
            jobs.append((f"strands {ds}", lambda ds=ds: StrandsSolver(ds).solve()))

    return jobs


def run(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Solve NYT puzzles headlessly.")
    parser.add_argument("--game", choices=GAMES + ["all"], default="all")
    parser.add_argument("--date", type=valid_date, default=None,
                        help="YYYY-MM-DD (Spelling Bee only; defaults to today)")
    parser.add_argument("--difficulty", choices=["easy", "medium", "hard", "all"], default="all",
                        help="Sudoku difficulty (default: all)")
    parser.add_argument("--backfill", action="store_true",
                        help=f"solve every available historical date ({', '.join(BACKFILL_GAMES)})")
    parser.add_argument("--since", type=valid_date, default=None,
                        help="earliest date to backfill (default: each game's full history)")
    parser.add_argument("--force", action="store_true",
                        help="re-solve dates already on disk (default: skip them)")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="seconds to sleep between puzzles during backfill (be polite to NYT)")
    args = parser.parse_args(argv)

    jobs = build_jobs(args)
    if not jobs:
        print("Nothing to solve.")
        return 0

    results = []
    for i, (label, job) in enumerate(jobs):
        try:
            job()
            results.append((label, True, None))
        except Exception as e:  # noqa: BLE001 - keep going so other games still run
            traceback.print_exc()
            results.append((label, False, str(e)))
        if args.delay and i < len(jobs) - 1:
            time.sleep(args.delay)

    failures = [r for r in results if not r[1]]
    print("\n=== Summary ===")
    for label, ok, err in results:
        print(f"  {'OK ' if ok else 'FAIL'}  {label}" + (f"  ({err})" if err else ""))
    print(f"{len(results) - len(failures)}/{len(results)} solved")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())
