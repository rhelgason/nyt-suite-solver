"""
Single, provider-agnostic LLM client shared by the solvers that genuinely need
one (Connections and the Mini crossword). Every LLM call in the project goes
through here, mirroring how ``scraping.py`` centralizes the NYT fetch.

Design principle #2 says solve algorithmically wherever possible and reach for an
LLM only when there is no reasonable deterministic approach. These two games are
that exception: grouping 16 trivia/wordplay words, and answering natural-language
crossword clues, have no clean algorithm. (The Mini still fills its grid with a
deterministic CSP; the LLM only supplies candidate answers.)

Reliability is the priority for the unattended daily run, so:

- The default provider is **GitHub Models**, which authenticates with the
  workflow's built-in ``GITHUB_TOKEN``. There is no separate API key to create,
  rotate, or let expire -- the token is minted fresh for every Actions run. That
  removes the single most common long-term failure mode of an LLM integration.
- If a free-tier key is present (``GEMINI_API_KEY``), it is used as an automatic
  fallback, so a GitHub Models rate-limit, outage, or model deprecation degrades
  to the backup instead of failing the run.
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

# Connections and crossword clues are lateral/wordplay reasoning, which the
# o-series reasoning models do markedly better than gpt-4o. We try a reasoning
# model first and fall back to gpt-4o if it is unavailable or rate-limited, so
# quality goes up without risking the run. Override the whole chain with a
# comma-separated GITHUB_MODELS_MODEL if desired.
GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
MODEL_CHAIN = [m.strip() for m in os.environ.get(
    "GITHUB_MODELS_MODEL", "openai/o4-mini,openai/gpt-4o").split(",") if m.strip()]
# `or` (not a default arg) so an empty env value from an unset CI variable still
# falls back to the default instead of becoming an invalid model name
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash"


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


def _github_models(system: Optional[str], prompt: str, max_tokens: int) -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_MODELS_TOKEN")
    if not token:
        raise LLMError("GITHUB_TOKEN not set")
    last_error = None
    for model in MODEL_CHAIN:  # strongest first, gpt-4o as the safe fallback
        try:
            return _github_call(token, model, system, prompt, max_tokens)
        except _RateLimited:
            raise  # same account -> other models are rate-limited too; let complete() wait
        except requests.RequestException as e:
            last_error = e
    raise last_error if last_error else LLMError("no models configured")


def _gemini(system: Optional[str], prompt: str, max_tokens: int) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY not set")
    body: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": max_tokens},
    }
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"Content-Type": "application/json"},
        params={"key": key},
        json=body,
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code == 429:
        raise _RateLimited(_retry_after(resp), resp.text[:600])
    if not resp.ok:  # surface the body (never the key) so the reason is visible
        raise requests.HTTPError(f"gemini {GEMINI_MODEL} {resp.status_code}: {resp.text[:300]}")
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


# Ordered by preference: GitHub Models (no external secret) first, then any
# configured free-tier fallback. A provider raises LLMError if its credential is
# absent, so unconfigured ones are skipped cleanly.
Provider = Callable[[Optional[str], str, int], str]
PROVIDERS: List[Provider] = [_github_models, _gemini]

# set by complete() when the last failure was a rate limit, so a bulk caller
# (backfill) can stop early instead of grinding through a throttled quota
_last_call_rate_limited = False


def available() -> bool:
    """True if at least one provider has a credential configured."""
    return bool(
        os.environ.get("GITHUB_TOKEN")
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
    and surrounding prose by falling back to the first balanced {...} or [...]."""
    text = text.strip()
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
