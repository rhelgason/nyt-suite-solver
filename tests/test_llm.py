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


def test_extract_json_strips_reasoning_think_block():
    text = '<think>Let me reason... maybe {"wrong": 1}</think>\n{"group": ["A"]}'
    assert llm._extract_json(text) == {"group": ["A"]}


def test_available_reflects_env(monkeypatch):
    for var in ("GROQ_API_KEY", "GITHUB_TOKEN", "GITHUB_MODELS_TOKEN", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert not llm.available()
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert llm.available()


def test_groq_leads_provider_order():
    assert llm.PROVIDERS[0] is llm._groq


def test_groq_posts_and_parses(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "tok")
    monkeypatch.setenv("GROQ_MODEL", "pinned-model")  # pin -> skip discovery
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["model"] = json["model"]
        return _FakeResp("grouped")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    assert llm._groq(None, "hi", 256) == "grouped"
    assert "api.groq.com" in captured["url"]
    assert captured["model"] == "pinned-model"


def test_groq_missing_key_raises_llm_error(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(llm.LLMError):
        llm._groq(None, "hi", 256)


def test_groq_falls_through_its_model_chain(monkeypatch):
    # a deprecated/removed primary model must fall through to the next in the chain
    monkeypatch.setenv("GROQ_API_KEY", "tok")
    monkeypatch.setattr(llm, "_models_for", lambda name: ["big-model", "small-model"])
    calls = []

    def fake_call(key, model, system, prompt, max_tokens):
        calls.append(model)
        if model == "big-model":
            raise llm.requests.RequestException("model removed")
        return "ok"

    monkeypatch.setattr(llm, "_groq_call", fake_call)
    assert llm._groq(None, "hi", 100) == "ok"
    assert calls == ["big-model", "small-model"]


def test_rank_models_orders_by_reasoning_then_size_then_version():
    ids = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile",
           "deepseek-r1-distill-llama-70b", "whisper-large-v3", "llama-guard-4-12b"]
    ranked = llm._rank_models(ids, llm._GROQ_FAMILIES)
    assert ranked[0] == "deepseek-r1-distill-llama-70b"   # reasoning wins
    assert ranked[1] == "llama-3.3-70b-versatile"          # 70b > 8b
    assert ranked[2] == "llama-3.1-8b-instant"
    assert "whisper-large-v3" not in ranked and "llama-guard-4-12b" not in ranked  # non-chat dropped


def test_rank_models_drops_off_family_ids():
    ranked = llm._rank_models(["some-random-model-70b", "llama-3.3-70b-versatile"], llm._GROQ_FAMILIES)
    assert ranked == ["llama-3.3-70b-versatile"]


def test_models_for_env_override_skips_discovery(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "a, b ,c")
    # discovery must NOT run when pinned
    monkeypatch.setattr(llm, "_discover_groq", lambda key: (_ for _ in ()).throw(AssertionError("called")))
    llm._DISCOVERY_CACHE.pop("groq", None)
    assert llm._models_for("groq") == ["a", "b", "c"]


def test_models_for_discovers_then_appends_static(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    llm._DISCOVERY_CACHE.pop("groq", None)
    monkeypatch.setattr(llm, "_PROVIDER_MODELS", dict(llm._PROVIDER_MODELS,
                        groq=(("GROQ_MODEL",), ["static-x"], lambda: ["disc-1", "disc-2"])))
    assert llm._models_for("groq") == ["disc-1", "disc-2", "static-x"]


def test_models_for_falls_back_to_static_on_discovery_failure(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    llm._DISCOVERY_CACHE.pop("groq", None)

    def boom():
        raise llm.requests.RequestException("catalog down")

    monkeypatch.setattr(llm, "_PROVIDER_MODELS", dict(llm._PROVIDER_MODELS,
                        groq=(("GROQ_MODEL",), ["static-x", "static-y"], boom)))
    assert llm._models_for("groq") == ["static-x", "static-y"]


class _JsonResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_discover_groq_parses_and_ranks_catalog(monkeypatch):
    payload = {"data": [{"id": "llama-3.3-70b-versatile"}, {"id": "whisper-large-v3"},
                        {"id": "deepseek-r1-distill-llama-70b"}, {"id": "llama-3.1-8b-instant"}]}
    monkeypatch.setattr(llm.requests, "get",
                        lambda url, headers=None, params=None, timeout=None: _JsonResp(payload))
    ranked = llm._discover_groq("key")
    assert ranked[0] == "deepseek-r1-distill-llama-70b"  # reasoning first
    assert "whisper-large-v3" not in ranked              # non-chat filtered out
    assert ranked[-1] == "llama-3.1-8b-instant"          # smallest last


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
    def __init__(self, content, status_code=200, headers=None, text=""):
        self._content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    @property
    def ok(self):
        return self.status_code < 400

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


def test_rate_limited_primary_falls_through_without_waiting(monkeypatch):
    slept = []
    monkeypatch.setattr(llm.time, "sleep", lambda s: slept.append(s))

    def limited(system, prompt, max_tokens):
        raise llm._RateLimited(30.0)

    def ok(system, prompt, max_tokens):
        return "second"

    monkeypatch.setattr(llm, "PROVIDERS", [limited, ok])
    assert llm.complete("hi") == "second"
    assert slept == []                 # used the fallback immediately, did not wait
    assert not llm.was_rate_limited()  # a successful call is not "rate limited"


def test_was_rate_limited_set_after_exhaustion(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    def limited(system, prompt, max_tokens):
        raise llm._RateLimited(1.0)

    monkeypatch.setattr(llm, "PROVIDERS", [limited])
    with pytest.raises(llm.LLMError):
        llm.complete("hi")
    assert llm.was_rate_limited()


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
    monkeypatch.setattr(llm, "_models_for", lambda name: ["openai/o4-mini", "openai/gpt-4o"])
    calls = []

    def fake_call(token, model, system, prompt, max_tokens):
        calls.append(model)
        if model == "openai/o4-mini":
            raise llm.requests.RequestException("model unavailable")
        return "recovered"

    monkeypatch.setattr(llm, "_github_call", fake_call)
    assert llm._github_models(None, "hi", 100) == "recovered"
    assert calls == ["openai/o4-mini", "openai/gpt-4o"]


def test_github_models_falls_through_to_next_tier_on_rate_limit(monkeypatch):
    # a rate limit on the premium model must NOT block the standard-tier fallback
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(llm, "_models_for", lambda name: ["openai/o4-mini", "openai/gpt-4o-mini"])
    calls = []

    def fake_call(token, model, system, prompt, max_tokens):
        calls.append(model)
        if model == "openai/o4-mini":
            raise llm._RateLimited(5.0)
        return "standard"

    monkeypatch.setattr(llm, "_github_call", fake_call)
    assert llm._github_models(None, "hi", 100) == "standard"
    assert calls == ["openai/o4-mini", "openai/gpt-4o-mini"]


def test_github_models_raises_rate_limited_only_when_all_models_are(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setattr(llm, "_models_for", lambda name: ["a", "b"])

    def fake_call(token, model, system, prompt, max_tokens):
        raise llm._RateLimited(1.0)

    monkeypatch.setattr(llm, "_github_call", fake_call)
    with pytest.raises(llm._RateLimited):
        llm._github_models(None, "hi", 100)
