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
# a hard cap so a model that keeps repeating itself cannot loop forever
MAX_ITERATIONS = 12

SYSTEM_PROMPT = (
    "You are an expert NYT Connections player. You are given the remaining words "
    "and must find one group of exactly four that share a hidden connection "
    "(wordplay, category, shared prefix/suffix, etc.). Respond ONLY with JSON."
)


def build_prompt(remaining: List[str], tried: List[List[str]], one_away: Optional[List[str]]) -> str:
    lines = [
        f"Remaining words: {', '.join(remaining)}",
        "",
        "Pick the four words you are MOST confident form a single group, and name "
        "the connection.",
    ]
    if tried:
        lines.append("")
        lines.append("These guesses were already wrong, do not repeat them:")
        for guess in tried:
            lines.append(f"  - {', '.join(guess)}")
    if one_away:
        lines.append("")
        lines.append(f"Your last guess ({', '.join(one_away)}) was ONE AWAY: exactly "
                     "three of those belong together. Swap one word.")
    lines.append("")
    lines.append('Respond as JSON: {"group": ["W1","W2","W3","W4"], "connection": "..."}')
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

    def play(self) -> None:
        """Play the game against the secret groups, one guess at a time, within
        the four-mistake budget. The LLM only ever sees the remaining words."""
        remaining_words = list(self.words)
        remaining_groups = list(self.true_groups)
        tried: List[List[str]] = []
        one_away_hint: Optional[List[str]] = None

        for _ in range(MAX_ITERATIONS):
            if self.mistakes >= MAX_MISTAKES or not remaining_groups:
                break

            # last four remaining are forced -- no need to spend a guess/LLM call
            if len(remaining_words) == GROUP_SIZE:
                guess = set(remaining_words)
            else:
                prompt = build_prompt(remaining_words, tried, one_away_hint)
                response = llm.complete_json(prompt, system=SYSTEM_PROMPT, max_tokens=256)
                raw = [str(w).upper() for w in response.get("group", [])]
                guess = {w for w in raw if w in remaining_words}
                if len(guess) != GROUP_SIZE:
                    # malformed / hallucinated words: count as a mistake and move on
                    self.mistakes += 1
                    self.guess_log.append({"guess": raw, "result": "invalid"})
                    continue

            one_away_hint = None
            idx = self._match(guess, remaining_groups)
            if idx is not None:
                title, group = remaining_groups.pop(idx)
                for word in group:
                    remaining_words.remove(word)
                self.groups_found += 1
                self.guess_log.append({"guess": sorted(guess), "result": "correct", "group": title})
            else:
                self.mistakes += 1
                tried.append(sorted(guess))
                if self._one_away(guess, remaining_groups):
                    one_away_hint = sorted(guess)
                self.guess_log.append({"guess": sorted(guess), "result": "wrong",
                                       "one_away": one_away_hint is not None})

        self.solved = self.groups_found == NUM_GROUPS

    def solve(self) -> None:
        date = datetime.strptime(self.ds, "%Y-%m-%d")
        print(f"Solving Connections for {date.strftime('%B %d, %Y')}:\n")

        start = time()
        try:
            self.play()
        except llm.LLMError as e:
            print(f"LLM unavailable, recording unsolved: {e}")
        end = time()

        for entry in self.guess_log:
            mark = {"correct": "OK  ", "wrong": "X   ", "invalid": "??  "}.get(entry["result"], "")
            print(f"  {mark}{', '.join(entry['guess'])}")
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
