import argparse

import pytest

import cli


def _args(**overrides):
    base = dict(game="all", date=None, difficulty="all", backfill=False)
    base.update(overrides)
    return argparse.Namespace(**base)


def test_build_jobs_all_today(monkeypatch):
    monkeypatch.setattr(cli, "today_ds", lambda: "2026-01-01")
    labels = [label for label, _ in cli.build_jobs(_args())]
    assert labels == [
        "letter-boxed 2026-01-01",
        "spelling-bee 2026-01-01",
        "sudoku easy 2026-01-01",
        "sudoku medium 2026-01-01",
        "sudoku hard 2026-01-01",
        "wordle easy 2026-01-01",
        "wordle hard 2026-01-01",
        "strands 2026-01-01",
    ]


def test_build_jobs_past_date_skips_today_only_games(monkeypatch):
    monkeypatch.setattr(cli, "today_ds", lambda: "2026-01-01")
    # Letter Boxed and Sudoku have no archive; Spelling Bee and Wordle do
    labels = [label for label, _ in cli.build_jobs(_args(date="2025-12-01"))]
    assert labels == [
        "spelling-bee 2025-12-01",
        "wordle easy 2025-12-01",
        "wordle hard 2025-12-01",
        "strands 2025-12-01",
    ]


def test_build_jobs_sudoku_single_difficulty(monkeypatch):
    monkeypatch.setattr(cli, "today_ds", lambda: "2026-01-01")
    labels = [label for label, _ in cli.build_jobs(_args(game="sudoku", difficulty="hard"))]
    assert labels == ["sudoku hard 2026-01-01"]


def test_backfill_rejected_for_non_spelling_bee():
    with pytest.raises(SystemExit):
        cli.build_jobs(_args(game="sudoku", backfill=True))


def test_backfill_uses_archive_dates(monkeypatch):
    monkeypatch.setattr(cli, "spelling_bee_archive_dates", lambda: ["2026-07-20", "2026-07-21"])
    labels = [label for label, _ in cli.build_jobs(_args(game="spelling-bee", backfill=True))]
    assert labels == ["spelling-bee 2026-07-20", "spelling-bee 2026-07-21"]


class _FakeSolver:
    def __init__(self, *args, **kwargs):
        pass

    def solve(self):
        pass


class _BoomSolver(_FakeSolver):
    def solve(self):
        raise RuntimeError("scrape failed")


def _stub_solvers(monkeypatch, sudoku=_FakeSolver):
    monkeypatch.setattr(cli, "today_ds", lambda: "2026-01-01")
    monkeypatch.setattr(cli, "LetterBoxedSolver", _FakeSolver)
    monkeypatch.setattr(cli, "SpellingBeeSolver", _FakeSolver)
    monkeypatch.setattr(cli, "SudokuSolver", sudoku)
    monkeypatch.setattr(cli, "WordleSolver", _FakeSolver)
    monkeypatch.setattr(cli, "StrandsSolver", _FakeSolver)


def test_run_all_ok(monkeypatch, capsys):
    _stub_solvers(monkeypatch)
    assert cli.run(["--game", "all"]) == 0
    assert "8/8 solved" in capsys.readouterr().out  # LB + SB + 3 sudoku + 2 wordle + strands


def test_run_reports_failures_with_nonzero_exit(monkeypatch, capsys):
    _stub_solvers(monkeypatch, sudoku=_BoomSolver)  # the three sudoku jobs fail
    assert cli.run(["--game", "all"]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "5/8 solved" in out  # LB + SB + 2 wordle + strands succeed, 3 sudoku fail
