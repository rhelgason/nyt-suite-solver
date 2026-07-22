from datetime import datetime, timedelta
from display_utils import clear_terminal
from solvers.BaseSolver import BaseSolver
from solvers.scraping import fetch_json
from Spinner import Spinner
from time import time
from typing import Dict, List, Optional, Tuple

import math
import os

BASE_URL = "https://www.nytimes.com/svc/wordle/v2"
WORDS_FILE_PATH = "wordlist.txt"
WORD_LENGTH = 5
MAX_GUESSES = 6

# The opening guess has no feedback to react to, so information theory yields the
# same first guess every day: the word whose feedback splits the vocabulary into
# the most even (highest-entropy) partition. Precomputed once via
# best_opening_guess(load_words()) over wordlist.txt (8938 words) at 6.21 bits;
# recompute it if that list changes. Keeping it a constant makes every solve
# start instantly.
OPENER = "tares"

# feedback markers
GREEN, YELLOW, BLACK = "g", "y", "b"
EMOJI = {GREEN: "\U0001F7E9", YELLOW: "\U0001F7E8", BLACK: "⬛"}


def feedback(guess: str, solution: str) -> str:
    """Return Wordle feedback for a guess as a 5-char string of g/y/b, handling
    duplicate letters the way the game does (greens first, then yellows limited
    by each letter's remaining count in the solution)."""
    result = [BLACK] * WORD_LENGTH
    remaining: Dict[str, int] = {}
    for ch in solution:
        remaining[ch] = remaining.get(ch, 0) + 1

    for i in range(WORD_LENGTH):
        if guess[i] == solution[i]:
            result[i] = GREEN
            remaining[guess[i]] -= 1

    for i in range(WORD_LENGTH):
        if result[i] == GREEN:
            continue
        ch = guess[i]
        if remaining.get(ch, 0) > 0:
            result[i] = YELLOW
            remaining[ch] -= 1

    return "".join(result)


def filter_candidates(candidates: List[str], guess: str, observed: str) -> List[str]:
    """Keep only candidates that would have produced the observed feedback."""
    return [word for word in candidates if feedback(guess, word) == observed]


def expected_information(guess: str, candidates: List[str]) -> float:
    """Expected information (Shannon entropy, in bits) of a guess: how much, on
    average, its feedback narrows down the remaining candidates.

    Group the candidates by the feedback pattern the guess would produce; a guess
    that spreads them across many equally-likely patterns has high entropy and is
    expected to eliminate more of them.
    """
    n = len(candidates)
    if n == 0:
        return 0.0
    counts: Dict[str, int] = {}
    for answer in candidates:
        pattern = feedback(guess, answer)
        counts[pattern] = counts.get(pattern, 0) + 1
    entropy = 0.0
    for count in counts.values():
        p = count / n
        entropy -= p * math.log2(p)
    return entropy


def best_guess(candidates: List[str], allowed: List[str]) -> str:
    """Pick the guess in ``allowed`` that maximizes expected information about the
    remaining ``candidates``.

    - Hard mode passes ``allowed = candidates`` (only playable answers).
    - Easy mode passes the full vocabulary, so it may play a word it knows cannot
      be the answer when that word extracts more information.

    Ties are broken toward a guess that could itself be the answer (a free chance
    to win), then alphabetically for determinism.
    """
    if len(candidates) <= 2:
        return sorted(candidates)[0]

    candidate_set = set(candidates)
    best_word, best_entropy, best_possible = None, -1.0, False
    for guess in allowed:
        entropy = expected_information(guess, candidates)
        possible = guess in candidate_set
        if entropy > best_entropy + 1e-9:
            better = True
        elif entropy > best_entropy - 1e-9:  # effectively equal information
            better = (possible and not best_possible) or (
                possible == best_possible and (best_word is None or guess < best_word)
            )
        else:
            better = False
        if better:
            best_word, best_entropy, best_possible = guess, entropy, possible
    return best_word


def best_opening_guess(words: List[str]) -> str:
    """The information-theoretic opener: highest expected information over the
    whole vocabulary. Used to derive the OPENER constant."""
    return best_guess(words, words)


class WordleSolver(BaseSolver):
    OUTPUT_DIRECTORY_PATH = "solutions/wordle"

    def __init__(self, ds: str = None, hard: bool = True) -> None:
        super().__init__(ds)
        self.hard = hard
        self.solution: Optional[str] = None
        self.guesses: List[str] = []
        self.solved: bool = False
        self.scrape_puzzle()

    @property
    def mode(self) -> str:
        return "hard" if self.hard else "easy"

    def output_file_name(self) -> str:
        return f"{self.ds}_{self.mode}.json"

    def scrape_puzzle(self) -> None:
        fetching_str = "Fetching puzzle from NYT website..."
        clear_terminal()
        with Spinner(fetching_str):
            data = fetch_json(f"{BASE_URL}/{self.ds}.json")
            self.puzzle_id = data["id"]
            self.solution = data["solution"].lower()
        clear_terminal()
        print(fetching_str + " done!")

    def load_words(self) -> List[str]:
        # guess from a realistic human vocabulary (five-letter words), not an
        # official answer list; the scraped solution is only the feedback oracle
        words = set()
        with open(os.path.join("./", WORDS_FILE_PATH), "r") as f:
            for line in f:
                word = line.strip().lower()
                if len(word) == WORD_LENGTH and word.isalpha():
                    words.add(word)
        return sorted(words)

    def play(self, words: List[str]) -> Tuple[List[str], bool]:
        """Play the game against the known solution and return (guesses, solved).
        Hard mode only ever guesses still-possible answers; easy mode may guess
        any word to maximize information."""
        remaining = list(words)
        guesses: List[str] = []
        for turn in range(MAX_GUESSES):
            if turn == 0:
                guess = OPENER if OPENER in remaining else best_opening_guess(words)
            elif remaining:
                allowed = remaining if self.hard else words
                guess = best_guess(remaining, allowed)
            else:
                break  # the answer is outside our vocabulary; we cannot guess it
            guesses.append(guess)
            if guess == self.solution:
                return guesses, True
            remaining = filter_candidates(remaining, guess, feedback(guess, self.solution))
        return guesses, False

    def solve(self) -> None:
        date = datetime.strptime(self.ds, "%Y-%m-%d")
        print(f"Solving {self.mode}-mode Wordle for {date.strftime('%B %d, %Y')}:\n")

        start = time()
        self.guesses, self.solved = self.play(self.load_words())
        end = time()

        print(self.guesses_to_string())
        if self.solved:
            print(f"\nSolved in {len(self.guesses)} guesses.")
        else:
            print(f"\nCould not solve (answer was '{self.solution}').")

        self.write_solved_puzzle(start, end)

    def guesses_to_string(self) -> str:
        rows = []
        for guess in self.guesses:
            squares = "".join(EMOJI[c] for c in feedback(guess, self.solution))
            rows.append(f"{squares}  {guess}")
        return "\n".join(rows)

    def write_solved_puzzle(self, start: float, end: float) -> None:
        data = {
            "puzzle_id": self.puzzle_id,
            "ds": self.ds,
            "mode": self.mode,
            "solution": self.solution,
            "guesses": self.guesses,
            "num_guesses": len(self.guesses) if self.solved else None,
            "solved": self.solved,
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_solution(data)
