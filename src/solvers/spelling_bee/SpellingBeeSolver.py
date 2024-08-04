from datetime import datetime
from display_utils import clear_terminal, MAX_PERCENTAGE, should_update_progress_bar, solve_time_to_string, use_progress_bar
from menu_options import gen_date_enum, MenuOptions, SpellingBeeDateOptions
from time import time
from typing import List, Set

import json
import os
import re
import requests

BASE_URL = "https://www.nytimes.com/puzzles/spelling-bee"
HTML_DATA_REGEX = r'<script type="text\/javascript">window\.gameData = (.+)<\/script><\/div><div id="portal-editorial-content">'
WORDS_FILE_PATH = "all_words.txt"
NUM_LETTERS = 7
MIN_LENGTH = 4

"""
Scrapes the NYT Spelling Bee puzzle and solves it using
a trie data structure.
"""
class SpellingBeeSolver:
    ds: str = None

    letters: Set[str] = set()
    center: str = None
    words: List[str] = []
    pangrams: List[str] = []
    max_length: int = 0

    def __init__(self, ds: str = None) -> None:
        self.ds = ds or datetime.today().date().strftime("%Y-%m-%d")
        self.scrape_puzzle()
        return

    @staticmethod
    def use_date_options(self, option: SpellingBeeDateOptions) -> MenuOptions:
        dates = ['2024-08-03']
        return gen_date_enum(dates)
    
    def scrape_puzzle(self) -> None:
        fetching_str = f"Fetching puzzle from NYT website..."
        clear_terminal()
        print(fetching_str)

        response = requests.get(BASE_URL, self.ds)
        match = re.search(HTML_DATA_REGEX, response.text)
        if match:
            data = json.loads(match.group(1))
            puzzle_data = data['today']
            self.center = puzzle_data['centerLetter']
            self.letters = set(puzzle_data['validLetters'])
            clear_terminal()
            print(fetching_str + " done!")
        else:
            raise Exception("Failed to find game data.")

        clear_terminal()
        print(fetching_str + " done!")
    
    def puzzle_to_string(self) -> str:
        if len(self.letters) != NUM_LETTERS:
            raise Exception("Incorrect number of letters in puzzle.")
        self.letters.remove(self.center)
        letters = list(self.letters)
        letters = [x.upper() for x in letters]
        
        res = f"""
                 _____
                /     \\
          _____/   {letters[0]}   \\_____
         /     \\       /     \\
        /   {letters[1]}   \\_____/   {letters[2]}   \\
        \       /     \\       /
         \_____/   {self.center.upper()}   \\_____/
         /     \\       /     \\
        /   {letters[3]}   \\_____/   {letters[4]}   \\
        \       /     \\       /
         \_____/   {letters[5]}   \\_____/
               \       /
                \_____/
        """
        self.letters.add(self.center)
        return res
    
    def solve(self) -> None:
        print(f"Solving today's puzzle:")
        print(self.puzzle_to_string())

        # get all valid words
        start = time()
        last_update = start
        file_path = os.path.join('./', WORDS_FILE_PATH)
        with open(file_path, "rb") as f:
            num_lines = sum(1 for _ in f)
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, start=1):
                self.validate_word(line.strip())
                if should_update_progress_bar():
                    progress = int((line_num / num_lines) * MAX_PERCENTAGE)
                    use_progress_bar(progress, start, time())
        
        # print results
        end = time()
        use_progress_bar(MAX_PERCENTAGE, start, end)
        print(f"\n\n{len(self.words) + len(self.pangrams)} words found:")
        for word in self.pangrams:
            space = " " * (self.max_length - len(word) + 1)
            print("\t- " + word + space + "(PANGRAM)")
        for word in self.words:
            print("\t- " + word)

        print("\nPress ENTER to return to the main menu.")
        input()

    def validate_word(self, word: str) -> None:
        word = word.lower()
        if len(word) < MIN_LENGTH:
            return
        elif self.center not in word:
            return
        
        used_letters = set()
        for letter in word:
            if letter not in self.letters:
                return
            used_letters.add(letter)
        if (len(word) > self.max_length):
            self.max_length = len(word)

        if len(used_letters) == NUM_LETTERS:
            self.pangrams.append(word)
        else:
            self.words.append(word)
