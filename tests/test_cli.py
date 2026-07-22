import argparse

import pytest

import cli


def _args(**overrides):
    base = dict(game="all", date=None, difficulty="all", backfill=False,
                since=None, force=True, delay=0.0, limit=None)
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
        "connections 2026-01-01",
        "crossword 2026-01-01",
    ]


def test_build_jobs_past_date_skips_today_only_games(monkeypatch):
    monkeypatch.setattr(cli, "today_ds", lambda: "2026-01-01")
    # Letter Boxed and Sudoku have no archive; Spelling Bee and Wordle do
    labels = [label for label, _ in cli.build_jobs(_args(date="2025-12-01"))]
    # Letter Boxed, Sudoku and the Mini crossword are today-only; the rest have history
    assert labels == [
        "spelling-bee 2025-12-01",
        "wordle easy 2025-12-01",
        "wordle hard 2025-12-01",
        "strands 2025-12-01",
        "connections 2025-12-01",
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


def test_date_range_inclusive():
    assert cli.date_range("2026-01-01", "2026-01-03") == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert cli.date_range("2026-01-01", "2026-01-01") == ["2026-01-01"]


def test_wordle_backfill_honors_since_and_epoch(monkeypatch):
    monkeypatch.setattr(cli, "today_ds", lambda: "2026-01-03")
    # --since before the epoch is clamped to the epoch, both modes per day
    labels = [l for l, _ in cli.build_jobs(_args(game="wordle", backfill=True, since="2025-12-31"))]
    assert labels == [
        "wordle easy 2025-12-31", "wordle hard 2025-12-31",
        "wordle easy 2026-01-01", "wordle hard 2026-01-01",
        "wordle easy 2026-01-02", "wordle hard 2026-01-02",
        "wordle easy 2026-01-03", "wordle hard 2026-01-03",
    ]


def test_strands_backfill_before_epoch_clamped(monkeypatch):
    monkeypatch.setattr(cli, "today_ds", lambda: "2024-03-05")
    labels = [l for l, _ in cli.build_jobs(_args(game="strands", backfill=True, since="2024-01-01"))]
    assert labels == ["strands 2024-03-04", "strands 2024-03-05"]  # epoch is 2024-03-04


def test_connections_backfill_defaults_to_cap(monkeypatch):
    monkeypatch.setattr(cli, "today_ds", lambda: "2026-01-01")
    labels = [l for l, _ in cli.build_jobs(_args(game="connections", backfill=True))]
    assert len(labels) == cli.DEFAULT_LLM_BACKFILL_LIMIT  # capped by default
    assert labels[-1] == "connections 2026-01-01"          # oldest-first, so newest last


def test_connections_backfill_respects_limit(monkeypatch):
    monkeypatch.setattr(cli, "today_ds", lambda: "2023-06-20")
    labels = [l for l, _ in cli.build_jobs(_args(game="connections", backfill=True, limit=3))]
    # the 3 most recent dates, solved oldest-first
    assert labels == ["connections 2023-06-18", "connections 2023-06-19", "connections 2023-06-20"]


def test_crossword_backfill_rejected_today_only():
    with pytest.raises(SystemExit):
        cli.build_jobs(_args(game="crossword", backfill=True))


def test_backfill_skips_existing_unless_forced(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "today_ds", lambda: "2024-03-05")
    monkeypatch.setattr(cli.StrandsSolver, "OUTPUT_DIRECTORY_PATH", str(tmp_path))
    (tmp_path / "2024-03-04.json").write_text("{}")
    labels = [l for l, _ in cli.build_jobs(_args(game="strands", backfill=True, force=False))]
    assert labels == ["strands 2024-03-05"]  # 03-04 already on disk, skipped


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
    monkeypatch.setattr(cli, "ConnectionsSolver", _FakeSolver)
    monkeypatch.setattr(cli, "MiniCrosswordSolver", _FakeSolver)


def test_run_all_ok(monkeypatch, capsys):
    _stub_solvers(monkeypatch)
    assert cli.run(["--game", "all"]) == 0
    # LB + SB + 3 sudoku + 2 wordle + strands + connections + crossword
    assert "10/10 solved" in capsys.readouterr().out


def test_run_reports_failures_with_nonzero_exit(monkeypatch, capsys):
    _stub_solvers(monkeypatch, sudoku=_BoomSolver)  # the three sudoku jobs fail
    assert cli.run(["--game", "all"]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "7/10 solved" in out  # all but the 3 sudoku jobs succeed
