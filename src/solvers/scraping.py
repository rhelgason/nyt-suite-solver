from typing import Any, Dict

import json
import re
import requests

# NYT embeds each puzzle's data as a JSON blob in a window.gameData script tag.
# This single regex is shared by every solver so the scraping contract lives in
# exactly one place.
HTML_DATA_REGEX = r'<script type="text\/javascript">window\.gameData = (.+)<\/script><\/div><div id="portal-editorial-content">'

# A browser-like User-Agent avoids trivial bot blocking; the timeout keeps daily
# automated runs from hanging forever on a slow response.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}
REQUEST_TIMEOUT = 30
MAX_ATTEMPTS = 3


class PuzzleDataNotFound(Exception):
    """Raised when the NYT page could not be parsed into puzzle data."""


def parse_game_data(html: str, source: str = "") -> Dict[str, Any]:
    """Extract and decode the window.gameData JSON blob from raw page HTML."""
    match = re.search(HTML_DATA_REGEX, html)
    if not match:
        location = f" at {source}" if source else ""
        raise PuzzleDataNotFound(f"Failed to find game data{location}.")
    return json.loads(match.group(1))


def _get_with_retries(url: str):
    """GET a URL with browser-like headers, a timeout, and a few retries."""
    last_error = None
    for _ in range(MAX_ATTEMPTS):
        try:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            last_error = e
    raise PuzzleDataNotFound(f"Failed to fetch {url}: {last_error}")


def fetch_game_data(url: str) -> Dict[str, Any]:
    """Fetch a NYT puzzle page and return its parsed gameData dict.

    Retries transient request failures a few times before giving up so that a
    single flaky network moment does not fail an automated daily run.
    """
    return parse_game_data(_get_with_retries(url).text, url)


def fetch_json(url: str) -> Dict[str, Any]:
    """Fetch a NYT JSON API endpoint (e.g. Wordle) and return the decoded dict."""
    response = _get_with_retries(url)
    try:
        return response.json()
    except ValueError as e:
        raise PuzzleDataNotFound(f"Response from {url} was not valid JSON: {e}")
