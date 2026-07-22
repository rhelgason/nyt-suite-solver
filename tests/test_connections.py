import json

from solvers.connections import ConnectionsSolver as mod
from solvers.connections.ConnectionsSolver import ConnectionsSolver

PUZZLE = {
    "id": 100,
    "print_date": "2026-07-22",
    "categories": [
        {"title": "RED", "cards": [{"content": "APPLE", "position": 0}, {"content": "ROSE", "position": 1},
                                    {"content": "RUBY", "position": 2}, {"content": "BLOOD", "position": 3}]},
        {"title": "BALL", "cards": [{"content": "BASE", "position": 4}, {"content": "BASKET", "position": 5},
                                    {"content": "FOOT", "position": 6}, {"content": "VOLLEY", "position": 7}]},
        {"title": "CATS", "cards": [{"content": "LION", "position": 8}, {"content": "TIGER", "position": 9},
                                    {"content": "PUMA", "position": 10}, {"content": "LYNX", "position": 11}]},
        {"title": "SEAS", "cards": [{"content": "CORAL", "position": 12}, {"content": "BALTIC", "position": 13},
                                    {"content": "RED2", "position": 14}, {"content": "NORTH", "position": 15}]},
    ],
}


def _install(monkeypatch, responder):
    monkeypatch.setattr(mod, "fetch_json", lambda url: PUZZLE)
    monkeypatch.setattr(mod.llm, "complete_json", responder)


def _remaining(prompt):
    return set(prompt.split("Remaining words: ")[1].split("\n")[0].split(", "))


def _true_groups():
    return [{c["content"].upper() for c in cat["cards"]} for cat in PUZZLE["categories"]]


def test_scrape_builds_board_in_position_order(monkeypatch):
    _install(monkeypatch, lambda *a, **k: {"group": []})
    s = ConnectionsSolver("2026-07-22")
    assert s.words[0] == "APPLE" and s.words[15] == "NORTH"
    assert len(s.words) == 16
    assert len(s.true_groups) == 4


def test_perfect_play_solves_with_no_mistakes(monkeypatch):
    def perfect(prompt, system=None, max_tokens=256):
        rem = _remaining(prompt)
        for group in _true_groups():
            if group <= rem:
                return {"group": sorted(group)}
        return {"group": []}
    _install(monkeypatch, perfect)
    s = ConnectionsSolver("2026-07-22")
    s.play()
    assert s.solved and s.groups_found == 4 and s.mistakes == 0


def test_always_wrong_loses_after_four_mistakes(monkeypatch):
    def wrong(prompt, system=None, max_tokens=256):
        rem = sorted(_remaining(prompt))
        # deliberately mix groups so it is never a real category
        return {"group": [rem[0], rem[5], rem[10], rem[15]][:4]}
    _install(monkeypatch, wrong)
    s = ConnectionsSolver("2026-07-22")
    s.play()
    assert not s.solved and s.mistakes == 4


def test_one_away_is_flagged(monkeypatch):
    # guess three REDs plus one wrong word -> should be recorded as one-away
    def one_away(prompt, system=None, max_tokens=256):
        return {"group": ["APPLE", "ROSE", "RUBY", "BASE"]}
    _install(monkeypatch, one_away)
    s = ConnectionsSolver("2026-07-22")
    s.play()
    assert any(g.get("one_away") for g in s.guess_log)


def test_invalid_words_count_as_mistake(monkeypatch):
    def hallucinate(prompt, system=None, max_tokens=256):
        return {"group": ["ZZZ", "QQQ", "WWW", "XXX"]}
    _install(monkeypatch, hallucinate)
    s = ConnectionsSolver("2026-07-22")
    s.play()
    assert s.mistakes == 4 and not s.solved
    assert any(g["result"] == "invalid" for g in s.guess_log)


def test_solve_writes_file(monkeypatch, tmp_path):
    def perfect(prompt, system=None, max_tokens=256):
        rem = _remaining(prompt)
        for group in _true_groups():
            if group <= rem:
                return {"group": sorted(group)}
        return {"group": []}
    _install(monkeypatch, perfect)
    s = ConnectionsSolver("2026-07-22")
    s.OUTPUT_DIRECTORY_PATH = str(tmp_path)
    s.solve()
    data = json.load(open(f"{tmp_path}/2026-07-22.json"))
    assert data["solved"] is True
    assert data["groups_found"] == 4
    assert len(data["categories"]) == 4
