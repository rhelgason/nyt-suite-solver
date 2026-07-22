import json

from solvers.crossword import MiniCrosswordSolver as mod
from solvers.crossword.MiniCrosswordSolver import (
    MiniCrosswordSolver,
    build_slots,
    fill_grid,
    fill_grid_prefer_llm,
    greedy_partial,
)

# a 2x2 all-white grid: across HI / AT, down HA / IT
CLUES = {
    "A": [{"clueNum": 1, "clueStart": 0, "clueEnd": 1, "value": "greeting"},
          {"clueNum": 2, "clueStart": 2, "clueEnd": 3, "value": "located at"}],
    "D": [{"clueNum": 1, "clueStart": 0, "clueEnd": 2, "value": "laugh sound"},
          {"clueNum": 2, "clueStart": 1, "clueEnd": 3, "value": "pronoun"}],
}
CONTENT = {"results": [{
    "puzzle_id": 1,
    "puzzle_meta": {"width": 2, "height": 2},
    "print_date": "2026-07-22",
    "puzzle_data": {"clues": CLUES, "layout": [1, 1, 1, 1], "answers": ["H", "I", "A", "T"]},
}]}
LISTING = {"results": [{"puzzle_id": 1}]}


def test_build_slots_geometry():
    slots = {s.id: s for s in build_slots(2, CLUES)}
    assert slots["A1"].cells == [0, 1]      # across, step 1
    assert slots["A2"].cells == [2, 3]
    assert slots["D1"].cells == [0, 2]      # down, step width
    assert slots["D2"].cells == [1, 3]
    assert slots["D1"].length == 2


def test_fill_grid_solves_from_correct_candidates():
    slots = build_slots(2, CLUES)
    cands = {"A1": ["HI"], "A2": ["AT"], "D1": ["HA"], "D2": ["IT"]}
    grid = fill_grid(slots, cands)
    assert grid == {0: "H", 1: "I", 2: "A", 3: "T"}


def test_fill_grid_uses_crossings_to_disambiguate():
    slots = build_slots(2, CLUES)
    # A1 is ambiguous (HI or HO); the D2 crossing forces the I
    cands = {"A1": ["HO", "HI"], "A2": ["AT"], "D1": ["HA"], "D2": ["IT"]}
    grid = fill_grid(slots, cands)
    assert grid[1] == "I"


def test_fill_grid_returns_none_when_unsatisfiable():
    slots = build_slots(2, CLUES)
    cands = {"A1": ["HI"], "A2": ["AT"], "D1": ["HA"], "D2": ["ON"]}  # D2 conflicts
    assert fill_grid(slots, cands) is None


def test_greedy_partial_fills_what_it_can():
    slots = build_slots(2, CLUES)
    cands = {"A1": ["HI"], "A2": [], "D1": [], "D2": []}
    grid = greedy_partial(slots, cands)
    assert grid[0] == "H" and grid[1] == "I"  # A1 placed; others left blank
    assert 2 not in grid or grid.get(2) is None


def test_prefer_llm_recovers_unanswered_slot_from_crossings():
    slots = build_slots(2, CLUES)
    # D2 is unanswered by the model; its letters must come from the crossings, and
    # the correct answers A1/A2/D1 must NOT be overwritten to patch it
    llm = {"A1": ["HI"], "A2": ["AT"], "D1": ["HA"], "D2": []}
    grid = fill_grid_prefer_llm(slots, llm, {2: ["IT", "ON"]})
    assert grid == {0: "H", 1: "I", 2: "A", 3: "T"}


def test_prefer_llm_never_overwrites_correct_answer_for_a_bad_one():
    slots = build_slots(2, CLUES)
    # D2's model answer ON conflicts with the correct crossings; with no dictionary
    # rescue it is left unplaced rather than corrupting A1/A2/D1
    llm = {"A1": ["HI"], "A2": ["AT"], "D1": ["HA"], "D2": ["ON"]}
    grid = fill_grid_prefer_llm(slots, llm, {})
    assert grid[0] == "H" and grid[1] == "I" and grid[2] == "A"  # correct cells kept


def _install(monkeypatch):
    monkeypatch.setattr(mod, "fetch_json",
                        lambda url: LISTING if "puzzles.json" in url else CONTENT)
    # isolate from wordlist.txt so only the mocked LLM candidates matter
    monkeypatch.setattr(MiniCrosswordSolver, "load_dictionary", lambda self, lengths: {})


def test_solve_writes_full_solution(monkeypatch, tmp_path):
    _install(monkeypatch)
    monkeypatch.setattr(mod.llm, "complete_json",
                        lambda *a, **k: {"A1": ["HI"], "A2": ["AT"], "D1": ["HA"], "D2": ["IT"]})
    s = MiniCrosswordSolver("2026-07-22")
    s.OUTPUT_DIRECTORY_PATH = str(tmp_path)
    s.solve()
    data = json.load(open(f"{tmp_path}/2026-07-22.json"))
    assert data["solved"] is True
    assert data["cells_correct"] == 4 and data["cells_total"] == 4


def test_solve_scores_partial_when_llm_incomplete(monkeypatch, tmp_path):
    _install(monkeypatch)
    # only one across answered, no way to complete -> partial credit, not a crash
    monkeypatch.setattr(mod.llm, "complete_json", lambda *a, **k: {"A1": ["HI"]})
    s = MiniCrosswordSolver("2026-07-22")
    s.OUTPUT_DIRECTORY_PATH = str(tmp_path)
    s.solve()
    data = json.load(open(f"{tmp_path}/2026-07-22.json"))
    assert data["solved"] is False
    assert 0 < data["cells_correct"] < 4


def test_solve_records_unsolved_when_llm_unavailable(monkeypatch, tmp_path):
    _install(monkeypatch)
    def boom(*a, **k):
        raise mod.llm.LLMError("no provider")
    monkeypatch.setattr(mod.llm, "complete_json", boom)
    s = MiniCrosswordSolver("2026-07-22")
    s.OUTPUT_DIRECTORY_PATH = str(tmp_path)
    s.solve()  # must not raise
    data = json.load(open(f"{tmp_path}/2026-07-22.json"))
    assert data["solved"] is False
