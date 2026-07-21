from datetime import datetime, timedelta
from display_utils import clear_terminal, MAX_PERCENTAGE, should_update_progress_bar, use_progress_bar
from solvers.BaseSolver import BaseSolver
from solvers.scraping import fetch_game_data
from Spinner import Spinner
from time import time
from trie.Trie import Trie
from typing import Dict, List, Set

import os
import sys

BASE_URL = "https://www.nytimes.com/puzzles/letter-boxed"
WORDS_FILE_PATH = "wordlist_small.txt"

NUM_SIDES = 4
NUM_LETTERS_PER_SIDE = 3
MIN_LENGTH = 3
# the max length is actually 5, but we can almost always do better
MAX_WORDS = 2

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

    def scrape_puzzle(self) -> None:
        fetching_str = f"Fetching puzzle from NYT website..."
        clear_terminal()
        with Spinner(fetching_str):
            puzzle_data = fetch_game_data(BASE_URL)
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
        file_path = os.path.join('./', WORDS_FILE_PATH)
        with open(file_path, "rb") as f:
            num_lines = sum(1 for _ in f)
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, start=1):
                self.validate_word(line.strip())
        
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
        print("\nPress ENTER to return to the main menu.")
        input()
    
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

    def get_valid_solutions(self, start: float) -> None:
        self.answers = [[] for _ in range(MAX_WORDS)]
        self.get_valid_solutions_helper([], set(), start)
    
    def get_valid_solutions_helper(self, words: List[str], used_letters: Set[str], start: float) -> None:
        # if used all letters
        if len(used_letters) == NUM_LETTERS_PER_SIDE * NUM_SIDES:
            self.answers[len(words) - 1].append(words)
            return
        
        # end early if we have more words than best answer
        if len(words) >= MAX_WORDS:
            return

        # recurse on each possible next word
        next_words = self.words.root if len(words) == 0 else self.words.root.children[ord(words[-1][-1]) - ord('a') + 1]
        if next_words is None:
            return
        for i in range(next_words.size):
            # update progress bar
            if len(words) == 0 and should_update_progress_bar():
                progress = int((i / next_words.size) * MAX_PERCENTAGE)
                use_progress_bar(progress, start, time())

            next_word = next_words[i]
            self.get_valid_solutions_helper(words + [next_word], used_letters | set(next_word), start)
        
    def write_solved_puzzle(self, start: float, end: float) -> None:
        valid_answers = []
        invalid_answers = []
        shortest_answer_length = sys.maxsize
        for answers in self.answers:
            for answer in answers:
                is_valid = True
                for word in answer:
                    if not self.valid_words.contains(word):
                        is_valid = False
                        break
                if is_valid:
                    valid_answers.append(answer)
                    shortest_answer_length = min(shortest_answer_length, len(answer))
                else:
                    invalid_answers.append(answer)

        data = {
            "puzzle_id": self.puzzle_id,
            "ds": self.ds,
            "sides": [list(x.keys()) for x in self.letters],
            "valid_answers": valid_answers,
            "invalid_answers": invalid_answers,
            "shortest_answer_length": shortest_answer_length,
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_solution(data)

def letter_boxed() -> int:
    solver = LetterBoxedSolver()
    solver.solve()
