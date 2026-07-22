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

REQUEST_TIMEOUT = 60
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2.0

# Defaults are overridable by env so the model can be swapped without code changes.
# gpt-4o (not -mini) is the default: Connections and crossword clues need real
# world-knowledge and wordplay reasoning that the mini model gets wrong. Override
# with GITHUB_MODELS_MODEL if a different model is preferred or better rate-limited.
GITHUB_MODELS_URL = "https://models.github.ai/inference/chat/completions"
GITHUB_MODELS_MODEL = os.environ.get("GITHUB_MODELS_MODEL", "openai/gpt-4o")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")


class LLMError(Exception):
    """Raised when no configured provider could produce a completion."""


def _github_models(system: Optional[str], prompt: str, max_tokens: int) -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_MODELS_TOKEN")
    if not token:
        raise LLMError("GITHUB_TOKEN not set")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = requests.post(
        GITHUB_MODELS_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"model": GITHUB_MODELS_MODEL, "messages": messages,
              "temperature": 0, "max_tokens": max_tokens},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


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
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


# Ordered by preference: GitHub Models (no external secret) first, then any
# configured free-tier fallback. A provider raises LLMError if its credential is
# absent, so unconfigured ones are skipped cleanly.
Provider = Callable[[Optional[str], str, int], str]
PROVIDERS: List[Provider] = [_github_models, _gemini]


def available() -> bool:
    """True if at least one provider has a credential configured."""
    return bool(
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GITHUB_MODELS_TOKEN")
        or os.environ.get("GEMINI_API_KEY")
    )


def complete(prompt: str, system: Optional[str] = None, max_tokens: int = 1024) -> str:
    """Return a completion for ``prompt``, trying each provider in turn and
    retrying transient failures with backoff. Raises ``LLMError`` if every
    provider is unavailable or exhausts its retries."""
    errors = []
    for provider in PROVIDERS:
        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                return provider(system, prompt, max_tokens)
            except LLMError as e:
                last_error = e
                break  # credential missing -> do not retry this provider
            except (requests.RequestException, KeyError, ValueError, IndexError) as e:
                last_error = e
                if attempt < MAX_ATTEMPTS - 1:
                    time.sleep(BACKOFF_SECONDS * (attempt + 1))
        errors.append(f"{provider.__name__}: {last_error}")
    raise LLMError("all providers failed -> " + "; ".join(errors))


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
