import pytest
import requests

from solvers import scraping
from solvers.scraping import PuzzleDataNotFound, fetch_game_data, parse_game_data


def test_parse_game_data_valid(game_html):
    data = {"id": 7, "sides": ["ABC"]}
    assert parse_game_data(game_html(data), "src") == data


def test_parse_game_data_missing_raises():
    with pytest.raises(PuzzleDataNotFound):
        parse_game_data("<html>nothing here</html>", "src")


class _FakeResponse:
    def __init__(self, text, status=200):
        self.text = text
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("bad status")


def test_fetch_game_data_success(monkeypatch, game_html):
    data = {"id": 99}
    monkeypatch.setattr(
        scraping.requests, "get", lambda *a, **k: _FakeResponse(game_html(data))
    )
    assert fetch_game_data("http://example.test") == data


def test_fetch_game_data_retries_then_fails(monkeypatch):
    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise requests.ConnectionError("down")

    monkeypatch.setattr(scraping.requests, "get", boom)
    with pytest.raises(PuzzleDataNotFound):
        fetch_game_data("http://example.test")
    assert calls["n"] == scraping.MAX_ATTEMPTS
