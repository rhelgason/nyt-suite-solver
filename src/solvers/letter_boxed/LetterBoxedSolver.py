from datetime import datetime, timedelta
from display_utils import clear_terminal, MAX_PERCENTAGE, should_update_progress_bar, use_progress_bar
from solvers.BaseSolver import BaseSolver
from solvers.scraping import fetch_game_data, fetch_json, PuzzleDataNotFound
from Spinner import Spinner
from time import time
from trie.Trie import Trie
from typing import Dict, List, Set

import os

BASE_URL = "https://www.nytimes.com/puzzles/letter-boxed"
# Past boards are NOT on the HTML page (a date-suffixed page 404s), but they are
# served by this date-addressable JSON endpoint in the same shape the page embeds
# -- crucially including that day's own board-specific `dictionary`, so archived
# puzzles can be scored as well as solved. Available from ARCHIVE_EPOCH onwards.
ARCHIVE_URL = "https://www.nytimes.com/svc/letter-boxed/v1/{ds}.json"
ARCHIVE_EPOCH = "2019-01-06"  # puzzle #16; earlier dates 404
WORDS_FILE_PATH = "wordlist_small.txt"

NUM_SIDES = 4
NUM_LETTERS_PER_SIDE = 3
MIN_LENGTH = 3
# the max length NYT allows is 5, but we can almost always do better. The search
# is iteratively deepened (see get_valid_solutions), so raising this ceiling only
# costs time on the rare days that genuinely need the extra word.
MAX_WORDS = 4
# a deep search can find tens of thousands of solutions for one board, which
# would commit a multi-megabyte file every day. Log a representative sample per
# word count and keep the true totals alongside it.
MAX_LOGGED_ANSWERS = 50
# each extra word multiplies the search space by roughly a hundred, so an
# unlucky board could search for hours. This runs unattended every day: cap the
# whole search and log an honest "unsolved" rather than hanging the daily job.
SEARCH_BUDGET_SECONDS = 300

"""
Scrapes the NYT Letter Boxed puzzle and solves it, all backed
by a trie data structure.
"""
class LetterBoxedSolver(BaseSolver):
    OUTPUT_DIRECTORY_PATH = "solutions/letter_boxed"

    answers: List[List[List[str]]] = []
    letters: List[Dict[str, None]] = set()
    words: Trie = None
    valid_words: Trie = None

    def __init__(self, ds: str = None) -> None:
        super().__init__(ds)
        self.answers = [[] for _ in range(MAX_WORDS)]
        self.letters = []
        self.words = Trie()
        self.valid_words = Trie()
        self.scrape_puzzle()

    def fetch_puzzle_data(self) -> Dict:
        """Today's board from the puzzle page, any earlier one from the JSON
        archive. Today deliberately keeps using the page the daily run has always
        used, so the unattended path is unchanged."""
        if self.ds == datetime.today().date().strftime("%Y-%m-%d"):
            return fetch_game_data(BASE_URL)

        puzzle_data = fetch_json(ARCHIVE_URL.format(ds=self.ds))
        # never silently solve the wrong day: the archive echoes back the date it
        # served, so a mismatch means we would be writing bad history
        if puzzle_data.get("printDate") != self.ds:
            raise PuzzleDataNotFound(
                f"Letter Boxed archive returned {puzzle_data.get('printDate')!r} for {self.ds}"
            )
        return puzzle_data

    def scrape_puzzle(self) -> None:
        fetching_str = f"Fetching puzzle from NYT website..."
        clear_terminal()
        with Spinner(fetching_str):
            puzzle_data = self.fetch_puzzle_data()
            self.puzzle_id = puzzle_data['id']
            for side in puzzle_data['sides']:
                self.letters.append(dict.fromkeys(side.lower()))
            for word in puzzle_data['dictionary']:
                self.valid_words.add_word(word.lower())
        clear_terminal()
        print(fetching_str + " done!")
    
    def puzzle_to_string(self) -> str:
        if len(self.letters) != NUM_SIDES:
            raise Exception("Incorrect number of letters in puzzle.")
        for side in self.letters:
            if len(side) != NUM_LETTERS_PER_SIDE:
                raise Exception("Incorrect number of letters in side.")

        letters = []
        for side in self.letters:
            letters.append([x.upper() for x in list(side.keys())])
        res = f"""
            {letters[0][0]}      {letters[0][1]}      {letters[0][2]}
           _________________
          |                 |
        {letters[3][0]} |                 | {letters[1][0]}
          |                 |
        {letters[3][1]} |                 | {letters[1][1]}
          |                 |
        {letters[3][2]} |                 | {letters[1][2]}
          |_________________|
            {letters[2][0]}      {letters[2][1]}      {letters[2][2]}
        """
        return res
    
    def solve(self) -> None:
        date = datetime.strptime(self.ds, "%Y-%m-%d")
        print(f"Solving puzzle for {date.strftime('%B %d, %Y')}:")
        print(self.puzzle_to_string())

        # get all valid words
        start = time()
        self.load_solving_words()

        self.get_valid_solutions(start)
        end = time()
        use_progress_bar(MAX_PERCENTAGE, start, end)

        # print condensed results
        print(f"\n\n{sum([len(i) for i in self.answers])} possible words found:")
        for i, answers in enumerate(self.answers):
            if len(answers) == 0:
                continue
            print(f"\t- {i + 1} word solutions: " + str(answers))

        # output results to file
        self.write_solved_puzzle(start, end)

    def load_solving_words(self) -> None:
        # search only within a realistic human vocabulary (wordlist_small), NOT
        # NYT's full accepted dictionary. The dictionary is used afterwards only
        # to classify found solutions as valid/invalid, mirroring how Spelling
        # Bee scores against but never solves from the official answer list.
        file_path = os.path.join('./', WORDS_FILE_PATH)
        with open(file_path, 'r') as f:
            for line in f:
                self.validate_word(line.strip())

    def validate_word(self, word: str) -> None:
        word = word.lower()
        if len(word) < MIN_LENGTH:
            return
        
        curr_side = -1
        for letter in word:

            next_side = self.get_next_side(letter, curr_side)
            if next_side == -1:
                return
            curr_side = next_side
        self.words.add_word(word)
    
    def get_next_side(self, letter: str, exclude_set: int) -> int:
        if (exclude_set >= NUM_SIDES):
            raise Exception("Invalid side index for exclusion.")
        
        for i, side in enumerate(self.letters):
            if i != exclude_set and letter in side:
                return i
        return -1

    def is_accepted_answer(self, answer: List[str]) -> bool:
        """Whether NYT's dictionary accepts every word of a solution. Only these
        count towards the reported shortest solution."""
        return all(self.valid_words.contains(word) for word in answer)

    def get_valid_solutions(self, start: float) -> None:
        # Iteratively deepen: the score we report is the SHORTEST solution, so
        # once a board is solved in n words there is nothing to learn from
        # enumerating its n+1 word solutions -- and plenty to lose, as each extra
        # word multiplies the search space by roughly a hundred. Searching depth
        # by depth keeps the common case as fast as a 2-word-only search while
        # still solving the rare boards that need 3 or 4 words.
        deadline = start + SEARCH_BUDGET_SECONDS
        for max_depth in range(1, MAX_WORDS + 1):
            # a depth-n pass re-finds every shorter solution too, so start clean
            # rather than accumulating duplicates across passes
            self.answers = [[] for _ in range(MAX_WORDS)]
            self.get_valid_solutions_helper([], set(), start, max_depth, deadline)
            # stop at the first depth NYT would actually accept a solution from;
            # a board solvable only by words outside their dictionary is not solved
            if any(self.is_accepted_answer(a) for bucket in self.answers for a in bucket):
                return
            if time() > deadline:
                return

    def get_valid_solutions_helper(self, words: List[str], used_letters: Set[str], start: float, max_depth: int, deadline: float) -> None:
        # if used all letters
        if len(used_letters) == NUM_LETTERS_PER_SIDE * NUM_SIDES:
            self.answers[len(words) - 1].append(words)
            return

        # end early if we have more words than best answer
        if len(words) >= max_depth:
            return

        # recurse on each possible next word
        next_words = self.words.root if len(words) == 0 else self.words.root.children[ord(words[-1][-1]) - ord('a') + 1]
        if next_words is None:
            return
        for i in range(next_words.size):
            # abandon a runaway search. Checking the two outermost levels bounds
            # the overrun to a single shallow subtree without paying for a clock
            # read in the innermost loop
            if len(words) <= 1 and time() > deadline:
                return

            # update progress bar
            if len(words) == 0 and should_update_progress_bar():
                progress = int((i / next_words.size) * MAX_PERCENTAGE)
                use_progress_bar(progress, start, time())

            next_word = next_words[i]
            self.get_valid_solutions_helper(words + [next_word], used_letters | set(next_word), start, max_depth, deadline)
        
    def write_solved_puzzle(self, start: float, end: float) -> None:
        valid_answers = []
        invalid_answers = []
        shortest_answer_length = None
        for answers in self.answers:
            for answer in answers:
                if self.is_accepted_answer(answer):
                    valid_answers.append(answer)
                    if shortest_answer_length is None:
                        shortest_answer_length = len(answer)
                    else:
                        shortest_answer_length = min(shortest_answer_length, len(answer))
                else:
                    invalid_answers.append(answer)

        data = {
            "puzzle_id": self.puzzle_id,
            "ds": self.ds,
            "sides": [list(x.keys()) for x in self.letters],
            "valid_answers": valid_answers[:MAX_LOGGED_ANSWERS],
            "invalid_answers": invalid_answers[:MAX_LOGGED_ANSWERS],
            "num_valid_answers": len(valid_answers),
            "num_invalid_answers": len(invalid_answers),
            # null, not a sentinel, when no solution was found: the wordlist is a
            # realistic human vocabulary, so some boards legitimately go unsolved
            "shortest_answer_length": shortest_answer_length,
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_solution(data)
