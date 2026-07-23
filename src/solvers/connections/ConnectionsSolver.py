"""
NYT Connections solver.

Connections gives 16 words that partition into 4 secret groups of 4, joined by a
hidden theme (often wordplay, trivia, or a shared prefix/suffix -- not plain
synonymy). There is no reasonable deterministic algorithm for that semantic
leap, so per design principle #2 this is a legitimate LLM solver: the model
proposes groupings and we play the real game against them.

We solve from the model's own reasoning, never from the answer key: the scraped
``categories`` are used only to referee each guess and to score the result, the
same way the other solvers use NYT's answer data purely for validation.

The game is simulated exactly as a human plays it -- one group guessed at a time,
a budget of four mistakes, and "one away" feedback -- so the recorded result
reflects realistic performance rather than a trivial win.
"""
from datetime import datetime, timedelta
from time import time
from typing import Dict, List, Optional, Set, Tuple

from solvers.BaseSolver import BaseSolver
from solvers.scraping import fetch_json
from solvers import llm

BASE_URL = "https://www.nytimes.com/svc/connections/v2"
GROUP_SIZE = 4
NUM_GROUPS = 4
MAX_MISTAKES = 4
# cap the LLM calls per puzzle: one plan up front, then at most one re-plan per
# mistake -- bounds cost and keeps well under the free per-minute rate limit
MAX_CALLS = 5

SYSTEM_PROMPT = (
    "You are an expert NYT Connections player. The remaining words always split "
    "into groups of exactly four sharing a hidden connection -- often wordplay, a "
    "shared prefix/suffix, or trivia, NOT plain synonyms. Some words look like they "
    "fit several groups; that is the intended trap, so reason over the WHOLE board "
    "before committing. Respond ONLY with JSON."
)


def build_prompt(remaining: List[str], tried: List[List[str]], one_away: Optional[List[str]]) -> str:
    n_groups = len(remaining) // 4
    lines = [
        f"Remaining words ({len(remaining)}): {', '.join(remaining)}",
        "",
        f"These form {n_groups} group(s) of four. Work out the full split, then list "
        f"the groups ordered from the one you are MOST confident about to least, so "
        f"I can guess the surest first.",
    ]
    if tried:
        lines.append("")
        lines.append("Already-wrong guesses (a full group is NOT among these), do not repeat:")
        for guess in tried:
            lines.append(f"  - {', '.join(guess)}")
    if one_away:
        lines.append("")
        lines.append(f"Your guess {', '.join(one_away)} was ONE AWAY: exactly three of "
                     "those four belong together. Keep those three and swap the fourth.")
    lines.append("")
    lines.append('Respond as JSON: {"groups": [{"words": ["W1","W2","W3","W4"], '
                 '"connection": "..."}, ...]} ordered most-confident first.')
    return "\n".join(lines)


class ConnectionsSolver(BaseSolver):
    OUTPUT_DIRECTORY_PATH = "solutions/connections"

    def __init__(self, ds: str = None) -> None:
        super().__init__(ds)
        self.words: List[str] = []
        self.true_groups: List[Tuple[str, Set[str]]] = []  # (title, {words})
        self.solved: bool = False
        self.groups_found: int = 0
        self.mistakes: int = 0
        self.guess_log: List[dict] = []
        self.scrape_puzzle()

    def scrape_puzzle(self) -> None:
        print("Fetching puzzle from NYT website...")
        data = fetch_json(f"{BASE_URL}/{self.ds}.json")
        self.puzzle_id = data.get("id")
        cards = []
        for category in data["categories"]:
            words = {card["content"].upper() for card in category["cards"]}
            self.true_groups.append((category["title"], words))
            for card in category["cards"]:
                cards.append((card["position"], card["content"].upper()))
        # the board as a player sees it: words in on-screen position order
        self.words = [word for _, word in sorted(cards)]
        print("Fetching puzzle from NYT website... done!")

    def _match(self, guess: Set[str], remaining_groups: List[Tuple[str, Set[str]]]) -> Optional[int]:
        """Index of the true group the guess exactly matches, or None."""
        for i, (_, group) in enumerate(remaining_groups):
            if guess == group:
                return i
        return None

    def _one_away(self, guess: Set[str], remaining_groups: List[Tuple[str, Set[str]]]) -> bool:
        return any(len(guess & group) == GROUP_SIZE - 1 for _, group in remaining_groups)

    def _make_plan(self, remaining_words: List[str]) -> List[Tuple[List[str], str]]:
        """One LLM call: a full split of the remaining words into confidence-ordered
        groups. Returns [(words, connection), ...]; parsing tolerates junk."""
        prompt = build_prompt(remaining_words, self._tried, self._one_away_hint)
        # generous budget: reasoning models spend hidden tokens before the JSON
        response = llm.complete_json(prompt, system=SYSTEM_PROMPT, max_tokens=3000)
        groups = response.get("groups") if isinstance(response, dict) else None
        plan = []
        for g in (groups or []):
            words = [str(w).upper() for w in (g.get("words") or [])]
            plan.append((words, str(g.get("connection", ""))))
        return plan

    def _next_guess(self, plan, remaining_words, tried_sets):
        """Best untried, still-valid group from the current plan, or (None, '')."""
        remaining = set(remaining_words)
        for words, connection in plan:
            guess = {w for w in words if w in remaining}
            if len(guess) == GROUP_SIZE and frozenset(guess) not in tried_sets:
                return guess, connection
        return None, ""

    def play(self) -> None:
        """Play within the four-mistake budget. Plan the whole board once and guess
        the surest group; only re-plan (another call) after a wrong guess so a clean
        solve costs a single request. Never repeat a guess, and feed the model the
        wrong-guess and one-away history so it stops looping on the same idea."""
        remaining_words = list(self.words)
        remaining_groups = list(self.true_groups)
        self._tried: List[List[str]] = []
        self._one_away_hint: Optional[List[str]] = None
        tried_sets: Set[frozenset] = set()
        plan: List[Tuple[List[str], str]] = []
        calls = 0

        while self.mistakes < MAX_MISTAKES and remaining_groups:
            connection = ""
            if len(remaining_words) == GROUP_SIZE:  # last four are forced -- no call
                guess = set(remaining_words)
            else:
                guess, connection = self._next_guess(plan, remaining_words, tried_sets)
                if guess is None:  # plan exhausted -> replan with the latest feedback
                    if calls >= MAX_CALLS:
                        break
                    plan = self._make_plan(remaining_words)
                    calls += 1
                    guess, connection = self._next_guess(plan, remaining_words, tried_sets)
                    if guess is None:  # model returned nothing usable and new
                        self.mistakes += 1
                        self.guess_log.append({"guess": [], "result": "invalid"})
                        continue

            self._one_away_hint = None
            idx = self._match(guess, remaining_groups)
            if idx is not None:
                title, group = remaining_groups.pop(idx)
                for word in group:
                    remaining_words.remove(word)
                self.groups_found += 1
                plan = [(w, c) for w, c in plan if not (set(w) & group)]  # keep only disjoint
                self.guess_log.append({"guess": sorted(guess), "result": "correct",
                                       "group": title, "connection": connection})
            else:
                self.mistakes += 1
                tried_sets.add(frozenset(guess))
                self._tried.append(sorted(guess))
                if self._one_away(guess, remaining_groups):
                    self._one_away_hint = sorted(guess)
                plan = []  # force a re-plan next turn using the new feedback
                self.guess_log.append({"guess": sorted(guess), "result": "wrong",
                                       "connection": connection,
                                       "one_away": self._one_away_hint is not None})

        self.solved = self.groups_found == NUM_GROUPS

    def solve(self) -> None:
        date = datetime.strptime(self.ds, "%Y-%m-%d")
        print(f"Solving Connections for {date.strftime('%B %d, %Y')}:\n")
        print("Board: " + ", ".join(self.words))
        print("Secret groups:")
        for title, words in self.true_groups:
            print(f"  - {title}: {', '.join(sorted(words))}")
        print()

        start = time()
        try:
            self.play()
        except llm.LLMError as e:
            print(f"LLM unavailable, recording unsolved: {e}")
        end = time()

        for entry in self.guess_log:
            mark = {"correct": "OK  ", "wrong": "X   ", "invalid": "??  "}.get(entry["result"], "")
            note = ""
            if entry["result"] == "correct":
                note = f"  -> {entry.get('group', '')}"
            elif entry["result"] == "wrong":
                label = entry.get("connection") or "?"
                note = f'  (guessed "{label}"' + (", one away)" if entry.get("one_away") else ")")
            print(f"  {mark}{', '.join(entry['guess'])}{note}")
        if self.solved:
            print(f"\nSolved with {self.mistakes} mistake(s).")
        else:
            print(f"\nFound {self.groups_found}/{NUM_GROUPS} groups ({self.mistakes} mistakes).")

        self.write_solved_puzzle(start, end)

    def write_solved_puzzle(self, start: float, end: float) -> None:
        data = {
            "puzzle_id": self.puzzle_id,
            "ds": self.ds,
            "words": self.words,
            "categories": [{"title": title, "words": sorted(words)} for title, words in self.true_groups],
            "solved": self.solved,
            "groups_found": self.groups_found,
            "mistakes": self.mistakes,
            "guesses": self.guess_log,
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_solution(data)
