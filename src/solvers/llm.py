"""
Single, provider-agnostic LLM client shared by the solvers that genuinely need
one (Connections and the Mini crossword). Every LLM call in the project goes
through here, mirroring how ``scraping.py`` centralizes the NYT fetch.

Design principle #2 says solve algorithmically wherever possible and reach for an
LLM only when there is no reasonable deterministic approach. These two games are
that exception: grouping 16 trivia/wordplay words, and answering natural-language
crossword clues, have no clean algorithm. (The Mini still fills its grid with a
deterministic CSP; the LLM only supplies candidate answers.)

Reliability is the priority for the unattended daily run, so several providers are
tried in order and any missing-credential one is skipped:

- **Groq** (``GROQ_API_KEY``) leads when configured: its free tier is genuinely
  generous and it serves a strong model, so it is the most usable free option.
- **GitHub Models** (``GITHUB_TOKEN``) needs no external key -- the token is minted
  fresh for every Actions run, so there is nothing to rotate or expire -- but its
  free quota for premium/reasoning models is very small.
- **Gemini** (``GEMINI_API_KEY``) is a final fallback where the account is
  free-tier eligible (some are not: ``limit: 0``).
- All providers use temperature 0 for as-deterministic-as-an-LLM-gets output.
  Results are still not bit-reproducible; that is the documented cost of the
  exception.

If no provider is configured or all of them fail, ``complete`` raises
``LLMError`` -- callers catch it and record an unsolved result so one game's
outage never crashes the daily job.
"""
from typing import Any, Callable, List, Optional

import json
import os
import re
import time

import requests

REQUEST_TIMEOUT = 120  # reasoning models can take a while
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = 2.0
RATE_LIMIT_MAX_SLEEP = 65.0  # honor a 429 Retry-After up to about a minute

# Model selection is DYNAMIC so the project keeps working for years as models come
# and go. At run time each provider's live catalog is queried, the chat models are
# ranked (reasoning-capable and larger/newer first), and that ranking is what we
# try in order -- so a model being removed or downgraded just means the next best
# available model is used, with no code change. Discovery is best-effort: if a
# catalog cannot be reached we fall back to a small static list, so behavior is
# never worse than a fixed chain. Pinning an env var (GROQ_MODEL / GEMINI_MODEL /
# GITHUB_MODELS_MODEL, comma-separated) overrides discovery entirely.
GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
GITHUB_CATALOG_URL = "https://models.github.ai/catalog/models"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_CATALOG_URL = "https://api.groq.com/openai/v1/models"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"
DISCOVERY_TIMEOUT = 20

# Static fallbacks, used only if a catalog can't be reached.
GITHUB_STATIC_MODELS = ["openai/o4-mini", "openai/gpt-4o-mini"]
GROQ_STATIC_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
GEMINI_STATIC_MODELS = ["gemini-2.0-flash", "gemini-flash-latest"]

# Ranking inputs. Families keep discovery to real chat model lines; the non-chat
# and reasoning hints steer scoring. All matched case-insensitively as substrings.
_GROQ_FAMILIES = ("llama", "qwen", "deepseek", "gpt-oss", "mixtral", "mistral", "gemma", "kimi", "moonshot")
_GITHUB_FAMILIES = ("openai/", "meta/", "meta-llama", "mistral", "deepseek", "xai", "microsoft", "cohere", "ai21")
_GEMINI_FAMILIES = ("gemini",)
_NON_CHAT = ("whisper", "tts", "guard", "embed", "moderation", "transcrib", "playai",
             "rerank", "-audio", "-image", "image-", "-vision-")
_REASONING_HINTS = ("gpt-oss", "deepseek", "r1", "qwq", "reason", "think", "o1-", "o3-", "o4-")


class LLMError(Exception):
    """Raised when no configured provider could produce a completion."""


class _RateLimited(Exception):
    """A 429 from a provider; carries the server's Retry-After (seconds) if given
    plus a short detail string from the body for diagnostics."""
    def __init__(self, retry_after: Optional[float], detail: str = ""):
        super().__init__("rate limited")
        self.retry_after = retry_after
        self.detail = detail


def _is_reasoning(model: str) -> bool:
    """o-series models (o1/o3/o4...) use a different request shape: they take
    max_completion_tokens and reject a non-default temperature."""
    name = model.split("/")[-1]
    return len(name) >= 2 and name[0] == "o" and name[1].isdigit()


def _retry_after(resp) -> Optional[float]:
    """Seconds to wait from a 429, read from the Retry-After header or a Google
    RetryInfo detail (e.g. {"retryDelay": "17s"}); None if not provided."""
    header = resp.headers.get("Retry-After")
    if header and header.replace(".", "", 1).isdigit():
        return float(header)
    try:
        for detail in resp.json().get("error", {}).get("details", []):
            delay = detail.get("retryDelay")
            if isinstance(delay, str) and delay.endswith("s") and delay[:-1].replace(".", "", 1).isdigit():
                return float(delay[:-1])
    except (ValueError, AttributeError):
        pass
    return None


def _rank_models(ids: List[str], families: tuple) -> List[str]:
    """Rank a provider's catalog to chat models, best first: reasoning-capable
    models outrank others, then larger parameter counts, then newer versions.
    Non-chat models and lines outside ``families`` are dropped."""
    ranked = []
    for mid in ids:
        s = mid.lower()
        if any(bad in s for bad in _NON_CHAT):
            continue
        if families and not any(f in s for f in families):
            continue
        score = 0.0
        if _is_reasoning(mid) or any(r in s for r in _REASONING_HINTS):
            score += 10000
        size = re.search(r"(\d+)\s*b(?:[^a-z0-9]|$)", s)  # parameter count, e.g. 70b
        if size:
            score += min(int(size.group(1)), 999)
        version = re.search(r"(\d+)\.(\d+)", s)            # e.g. 3.3, 2.5
        if version:
            score += int(version.group(1)) * 5 + int(version.group(2)) * 0.5
        if any(p in s for p in ("preview", "experimental", "-exp", "beta")):
            score -= 3  # prefer stable releases when otherwise comparable
        ranked.append((score, mid))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [mid for _, mid in ranked]


def _discover_groq(key: str) -> List[str]:
    resp = requests.get(GROQ_CATALOG_URL, headers={"Authorization": f"Bearer {key}"},
                        timeout=DISCOVERY_TIMEOUT)
    resp.raise_for_status()
    ids = [m.get("id", "") for m in resp.json().get("data", []) if m.get("id")]
    return _rank_models(ids, _GROQ_FAMILIES)


def _discover_github(token: str) -> List[str]:
    resp = requests.get(GITHUB_CATALOG_URL,
                        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                        timeout=DISCOVERY_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    items = data if isinstance(data, list) else data.get("models", data.get("data", []))
    ids = [(m.get("id") or m.get("name")) for m in items if isinstance(m, dict)]
    return _rank_models([i for i in ids if i], _GITHUB_FAMILIES)


def _discover_gemini(key: str) -> List[str]:
    resp = requests.get(f"{GEMINI_BASE}/models", params={"key": key}, timeout=DISCOVERY_TIMEOUT)
    resp.raise_for_status()
    ids = []
    for m in resp.json().get("models", []):
        methods = m.get("supportedGenerationMethods") or m.get("supported_generation_methods") or []
        name = (m.get("name") or "").split("/")[-1]
        if name and (not methods or "generateContent" in methods):
            ids.append(name)
    return _rank_models(ids, _GEMINI_FAMILIES)


# provider name -> (env override vars, static fallback, discovery callable)
_PROVIDER_MODELS = {
    "groq": (("GROQ_MODEL",), GROQ_STATIC_MODELS,
             lambda: _discover_groq(os.environ.get("GROQ_API_KEY", ""))),
    "github": (("GITHUB_MODELS_MODEL",), GITHUB_STATIC_MODELS,
               lambda: _discover_github(os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_MODELS_TOKEN", ""))),
    "gemini": (("GEMINI_MODEL",), GEMINI_STATIC_MODELS,
               lambda: _discover_gemini(os.environ.get("GEMINI_API_KEY", ""))),
}
_DISCOVERY_CACHE: dict = {}  # provider -> resolved model list (per process)


def _models_for(name: str) -> List[str]:
    """Ordered models to try for a provider: an env override if pinned; otherwise
    the live-discovered ranking followed by the static fallback (deduped). Cached
    per process, and any discovery failure degrades to the static list."""
    env_names, static, discover = _PROVIDER_MODELS[name]
    for env_name in env_names:
        raw = os.environ.get(env_name)
        if raw:
            pinned = [m.strip() for m in raw.split(",") if m.strip()]
            if pinned:
                return pinned  # explicit override -> no discovery
    if name in _DISCOVERY_CACHE:
        return _DISCOVERY_CACHE[name]
    models = list(static)
    try:
        discovered = discover()
        if discovered:
            models = discovered + [m for m in static if m not in discovered]
    except Exception:  # noqa: BLE001 - discovery is best-effort; fall back to static
        pass
    _DISCOVERY_CACHE[name] = models
    return models


def _github_call(token: str, model: str, system: Optional[str], prompt: str, max_tokens: int) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": model, "messages": messages}
    if _is_reasoning(model):
        payload["max_completion_tokens"] = max_tokens  # must cover hidden reasoning tokens
    else:
        payload["max_tokens"] = max_tokens
        payload["temperature"] = 0
    resp = requests.post(
        GITHUB_MODELS_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code == 429:
        raise _RateLimited(_retry_after(resp), resp.text[:600])
    if not resp.ok:  # surface the body so the failure reason is visible in logs
        raise requests.HTTPError(f"github {model} {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"]


def _try_models(models: List[str], call_one: Callable[[str], str]) -> str:
    """Run ``call_one(model)`` for each model in order until one succeeds. A
    rate-limited, deprecated, or unavailable model falls through to the next, so no
    single model is a hard dependency. Raises the most informative error if all
    fail (a real error over a bare rate-limit)."""
    last_rate_limited = None
    last_other = None
    for model in models:
        try:
            return call_one(model)
        except _RateLimited as e:
            last_rate_limited = e
        except requests.RequestException as e:
            last_other = e
    if last_other is not None:
        raise last_other
    if last_rate_limited is not None:
        raise last_rate_limited
    raise LLMError("no models configured")


def _github_models(system: Optional[str], prompt: str, max_tokens: int) -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_MODELS_TOKEN")
    if not token:
        raise LLMError("GITHUB_TOKEN not set")
    return _try_models(_models_for("github"),
                       lambda m: _github_call(token, m, system, prompt, max_tokens))


def _gemini_call(key: str, model: str, system: Optional[str], prompt: str, max_tokens: int) -> str:
    body: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens},
    }
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"Content-Type": "application/json"},
        params={"key": key},
        json=body,
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code == 429:
        raise _RateLimited(_retry_after(resp), resp.text[:600])
    if not resp.ok:  # surface the body (never the key) so the reason is visible
        raise requests.HTTPError(f"gemini {model} {resp.status_code}: {resp.text[:300]}")
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _gemini(system: Optional[str], prompt: str, max_tokens: int) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY not set")
    return _try_models(_models_for("gemini"),
                       lambda m: _gemini_call(key, m, system, prompt, max_tokens))


def _groq_call(key: str, model: str, system: Optional[str], prompt: str, max_tokens: int) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(
        GROQ_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code == 429:
        raise _RateLimited(_retry_after(resp), resp.text[:600])
    if not resp.ok:  # surface the body (never the key) so the reason is visible
        raise requests.HTTPError(f"groq {model} {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"]


def _groq(system: Optional[str], prompt: str, max_tokens: int) -> str:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise LLMError("GROQ_API_KEY not set")
    return _try_models(_models_for("groq"),
                       lambda m: _groq_call(key, m, system, prompt, max_tokens))


# Provider order: Groq first (generous free tier + strong model), then GitHub
# Models (free, no external secret), then Gemini. A provider raises LLMError if its
# credential is absent, so unconfigured ones are skipped cleanly.
Provider = Callable[[Optional[str], str, int], str]
PROVIDERS: List[Provider] = [_groq, _github_models, _gemini]

# set by complete() when the last failure was a rate limit, so a bulk caller
# (backfill) can stop early instead of grinding through a throttled quota
_last_call_rate_limited = False


def available() -> bool:
    """True if at least one provider has a credential configured."""
    return bool(
        os.environ.get("GROQ_API_KEY")
        or os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_MODELS_TOKEN")
        or os.environ.get("GEMINI_API_KEY")
    )


def was_rate_limited() -> bool:
    """True if the most recent complete() ultimately failed to a rate limit."""
    return _last_call_rate_limited


def complete(prompt: str, system: Optional[str] = None, max_tokens: int = 1024) -> str:
    """Return a completion for ``prompt``. Each round tries every provider in
    order, so a rate-limited primary falls straight through to the fallback rather
    than waiting; only if ALL configured providers fail a round do we back off and
    retry. Raises ``LLMError`` if nothing is configured or every retry is spent."""
    global _last_call_rate_limited
    errors = []
    saw_rate_limit = False
    for attempt in range(MAX_ATTEMPTS):
        any_present = False       # at least one provider had a credential this round
        rate_limited = False
        retry_after = None
        for provider in PROVIDERS:
            try:
                _last_call_rate_limited = False
                return provider(system, prompt, max_tokens)
            except LLMError as e:
                errors.append(f"{provider.__name__}: {e}")  # missing credential -> skip
            except _RateLimited as e:
                any_present = True
                rate_limited = saw_rate_limit = True
                if e.retry_after is not None:
                    retry_after = e.retry_after
                errors.append(f"{provider.__name__}: rate limited{(' - ' + e.detail) if e.detail else ''}")
            except (requests.RequestException, KeyError, ValueError, IndexError) as e:
                any_present = True
                errors.append(f"{provider.__name__}: {e}")
        if not any_present:
            break  # nothing configured / all missing credentials -> do not spin
        if attempt < MAX_ATTEMPTS - 1:
            if rate_limited:
                time.sleep(min(retry_after if retry_after is not None
                               else BACKOFF_SECONDS * (attempt + 1), RATE_LIMIT_MAX_SLEEP))
            else:
                time.sleep(BACKOFF_SECONDS * (attempt + 1))
    _last_call_rate_limited = saw_rate_limit
    raise LLMError("all providers failed -> " + "; ".join(errors[-len(PROVIDERS):]))


def _extract_json(text: str) -> Any:
    """Best-effort JSON parse of an LLM response, tolerating markdown code fences
    and surrounding prose by falling back to the first balanced {...} or [...].
    Reasoning models emit a <think>...</think> block first, which is stripped."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise LLMError(f"response was not valid JSON: {text[:200]}")


def complete_json(prompt: str, system: Optional[str] = None, max_tokens: int = 1024) -> Any:
    """Like ``complete`` but parse the response as JSON (list or dict)."""
    return _extract_json(complete(prompt, system=system, max_tokens=max_tokens))
