import pytest

from solvers import llm


def test_extract_json_plain():
    assert llm._extract_json('{"a": 1}') == {"a": 1}
    assert llm._extract_json('[1, 2, 3]') == [1, 2, 3]


def test_extract_json_code_fence_and_prose():
    assert llm._extract_json('```json\n{"group": ["A"]}\n```') == {"group": ["A"]}
    assert llm._extract_json('Sure! Here is the answer:\n{"x": [1]}\nHope that helps.') == {"x": [1]}


def test_extract_json_raises_on_garbage():
    with pytest.raises(llm.LLMError):
        llm._extract_json("no json here at all")


def test_available_reflects_env(monkeypatch):
    for var in ("GITHUB_TOKEN", "GITHUB_MODELS_TOKEN", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert not llm.available()
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    assert llm.available()


def test_complete_falls_back_to_next_provider(monkeypatch):
    calls = []

    def broken(system, prompt, max_tokens):
        calls.append("broken")
        raise llm.LLMError("no credential")

    def working(system, prompt, max_tokens):
        calls.append("working")
        return "hello"

    monkeypatch.setattr(llm, "PROVIDERS", [broken, working])
    assert llm.complete("hi") == "hello"
    assert calls == ["broken", "working"]


def test_complete_raises_when_all_fail(monkeypatch):
    def broken(system, prompt, max_tokens):
        raise llm.LLMError("nope")

    monkeypatch.setattr(llm, "PROVIDERS", [broken])
    with pytest.raises(llm.LLMError):
        llm.complete("hi")
