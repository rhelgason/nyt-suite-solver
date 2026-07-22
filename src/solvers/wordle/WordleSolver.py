from datetime import datetime, timedelta
from display_utils import clear_terminal
from solvers.BaseSolver import BaseSolver
from solvers.scraping import fetch_json
from Spinner import Spinner
from time import time
from typing import Dict, List, Optional, Tuple

import os

BASE_URL = "https://www.nytimes.com/svc/wordle/v2"
WORDS_FILE_PATH = "wordlist.txt"
WORD_LENGTH = 5
MAX_GUESSES = 6
# a strong, letter-diverse fixed opener keeps the first guess O(1) instead of
# scoring every word in the pool
OPENER = "slate"

# feedback markers
GREEN, YELLOW, BLACK = "g", "y", "b"
EMOJI = {GREEN: "\U0001F7E9", YELLOW: "\U0001F7E8", BLACK: "⬛"}


def feedback(guess: str, solution: str) -> str:
    """Return Wordle feedback for a guess as a 5-char string of g/y/b, handling
    duplicate letters the same way the game does (greens first, then yellows are
    limited by the remaining count of each letter in the solution)."""
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


def choose_guess(candidates: List[str]) -> str:
    """Greedily pick the candidate whose feedback partitions the remaining
    candidates most evenly (minimizing the sum of squared bucket sizes, i.e. the
    expected remaining count). Ties break alphabetically for determinism."""
    if len(candidates) <= 2:
        return candidates[0]
    best_word, best_score = None, None
    for guess in candidates:
        buckets: Dict[str, int] = {}
        for other in candidates:
            pattern = feedback(guess, other)
            buckets[pattern] = buckets.get(pattern, 0) + 1
        score = sum(count * count for count in buckets.values())
        if best_score is None or score < best_score or (score == best_score and guess < best_word):
            best_word, best_score = guess, score
    return best_word


class WordleSolver(BaseSolver):
    OUTPUT_DIRECTORY_PATH = "solutions/wordle"

    def __init__(self, ds: str = None) -> None:
        super().__init__(ds)
        self.solution: Optional[str] = None
        self.guesses: List[str] = []
        self.solved: bool = False
        self.scrape_puzzle()

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

    def play(self, candidates: List[str]) -> Tuple[List[str], bool]:
        """Play the game against the known solution and return (guesses, solved)."""
        remaining = candidates
        candidate_set = set(candidates)
        guesses: List[str] = []
        for turn in range(MAX_GUESSES):
            if turn == 0 and OPENER in candidate_set:
                guess = OPENER
            elif remaining:
                guess = choose_guess(remaining)
            else:
                break  # the solution is outside our vocabulary; we cannot guess it
            guesses.append(guess)
            if guess == self.solution:
                return guesses, True
            remaining = filter_candidates(remaining, guess, feedback(guess, self.solution))
        return guesses, False

    def solve(self) -> None:
        date = datetime.strptime(self.ds, "%Y-%m-%d")
        print(f"Solving Wordle for {date.strftime('%B %d, %Y')}:\n")

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
            "solution": self.solution,
            "guesses": self.guesses,
            "num_guesses": len(self.guesses) if self.solved else None,
            "solved": self.solved,
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_solution(data)
