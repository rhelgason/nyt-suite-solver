from datetime import datetime, timedelta
from display_utils import clear_terminal, MAX_PERCENTAGE, should_update_progress_bar, use_progress_bar, use_spelling_bee_menu
from enum import Enum
from menu_options import gen_date_enum, MenuOptions, SpellingBeeDateOptions
from Spinner import Spinner
from time import time
from trie.Trie import Trie
from typing import Any, Dict, List

import json
import os
import re
import requests

BASE_URL = "https://www.nytimes.com/puzzles/letter-boxed"
HTML_DATA_REGEX = r'<script type="text\/javascript">window\.gameData = (.+)<\/script><\/div><div id="portal-editorial-content">'

WORDS_FILE_PATH = "wordlist.txt"
OUTPUT_DIRECTORY_PATH = "solutions/letter_boxed"
NUM_SIDES = 4
NUM_LETTERS_PER_SIDE = 3
MIN_LENGTH = 3

"""
Scrapes the NYT Letter Boxed puzzle and solves it, all backed
by a trie data structure.
"""
class LetterBoxedSolver:
    puzzle_id: int = None
    answers: List[str] = []
    ds: str = None

    letters: List[Dict[str, None]] = set()
    words: Trie = []

    def __init__(self, ds: str = None) -> None:
        self.answers = []
        self.ds = datetime.today().date().strftime("%Y-%m-%d")
        self.letters = []
        self.words = Trie()
        self.scrape_puzzle()
        return
    
    def scrape_puzzle(self) -> None:
        fetching_str = f"Fetching puzzle from NYT website..."
        clear_terminal()
        with Spinner(fetching_str):
            response = requests.get(BASE_URL)
            match = re.search(HTML_DATA_REGEX, response.text)
            print(match)
            if match:
                puzzle_data = json.loads(match.group(1))
                self.puzzle_id = puzzle_data['id']
                for side in puzzle_data['sides']:
                    self.letters.append(dict.fromkeys(side))
            else:
                raise Exception("Failed to find game data.")
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
            letters.append(list(side.keys()))
        res = f"""
            {letters[0][0]}      {letters[0][1]}      {letters[0][2]}
           _________________
          |                 |
        {letters[3][0]} |                 | {letters[1][0]}
          |                 |
        {letters[3][1]} |                 | {letters[1][2]}
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

        print("\nPress ENTER to return to the main menu.")
        input()

def letter_boxed() -> int:
    solver = LetterBoxedSolver()
    solver.solve()
