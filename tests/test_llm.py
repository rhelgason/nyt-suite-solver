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


def test_is_reasoning_detection():
    assert llm._is_reasoning("openai/o4-mini")
    assert llm._is_reasoning("openai/o3-mini")
    assert llm._is_reasoning("openai/o1")
    assert not llm._is_reasoning("openai/gpt-4o")
    assert not llm._is_reasoning("openai/gpt-4o-mini")


class _FakeResp:
    def __init__(self, content, status_code=200, headers=None):
        self._content = content
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_github_call_uses_reasoning_params(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(json)
        return _FakeResp("ok")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    llm._github_call("tok", "openai/o4-mini", None, "hi", 2000)
    assert captured["max_completion_tokens"] == 2000
    assert "temperature" not in captured and "max_tokens" not in captured


def test_github_call_uses_standard_params(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(json)
        return _FakeResp("ok")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    llm._github_call("tok", "openai/gpt-4o", None, "hi", 500)
    assert captured["max_tokens"] == 500 and captured["temperature"] == 0


def test_github_call_raises_rate_limited_on_429(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return _FakeResp("", status_code=429, headers={"Retry-After": "12"})

    monkeypatch.setattr(llm.requests, "post", fake_post)
    with pytest.raises(llm._RateLimited) as exc:
        llm._github_call("tok", "openai/gpt-4o", None, "hi", 100)
    assert exc.value.retry_after == 12.0


def test_complete_waits_and_retries_on_rate_limit(monkeypatch):
    slept = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))
    calls = {"n": 0}

    def flaky(system, prompt, max_tokens):
        calls["n"] += 1
        if calls["n"] == 1:
            raise llm._RateLimited(5.0)
        return "ok"

    monkeypatch.setattr(llm, "PROVIDERS", [flaky])
    assert llm.complete("hi") == "ok"
    assert slept == [5.0]  # honored the Retry-After before retrying


def test_github_models_falls_back_across_model_chain(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(llm, "MODEL_CHAIN", ["openai/o4-mini", "openai/gpt-4o"])
    calls = []

    def fake_call(token, model, system, prompt, max_tokens):
        calls.append(model)
        if model == "openai/o4-mini":
            raise llm.requests.RequestException("model unavailable")
        return "recovered"

    monkeypatch.setattr(llm, "_github_call", fake_call)
    assert llm._github_models(None, "hi", 100) == "recovered"
    assert calls == ["openai/o4-mini", "openai/gpt-4o"]
