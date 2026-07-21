import json
import os
import sys

import pytest

# The solvers pull in pynput via the interactive menu layer. Force its dummy
# backend so the modules import on a headless machine (e.g. CI) without needing
# a real or virtual display. Set before any solver import happens.
os.environ.setdefault("PYNPUT_BACKEND_KEYBOARD", "dummy")
os.environ.setdefault("PYNPUT_BACKEND_MOUSE", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def make_game_html(data):
    """Wrap a puzzle-data dict in the same window.gameData markup NYT serves."""
    return (
        '<script type="text/javascript">window.gameData = '
        + json.dumps(data)
        + "</script></div><div id=\"portal-editorial-content\">"
    )


@pytest.fixture
def game_html():
    return make_game_html


@pytest.fixture
def repo_root():
    return ROOT
