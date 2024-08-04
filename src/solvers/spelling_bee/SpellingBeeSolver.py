from datetime import datetime
from display_utils import clear_terminal, solve_time_to_string
from time import time
from typing import List, Set

import os

WORDS_FILE_PATH = "src/solvers/spelling_bee/all_words.txt"
NUM_LETTERS = 7
MIN_LENGTH = 4

"""
Scrapes the NYT Spelling Bee puzzle and solves it using
a trie data structure.
"""
class SpellingBeeSolver:
    # TODO: allow solving of archived boards
    ds: datetime = None

    # puzzle attributes
    letters: Set[str] = set()
    center: str = None
    words: List[str] = []
    pangrams: List[str] = []
    max_length: int = 0

    def __init__(self) -> None:
        self.ds = datetime.today()
        self.scrape_puzzle()
        return
    
    def scrape_puzzle(self) -> None:
        fetching_str = f"Fetching puzzle from NYT website..."
        clear_terminal()
        print(fetching_str)

        # TODO: scrape puzzle from NYT site
        self.letters = set(["n", "a", "c", "i", "l", "o", "v"])
        self.center = "v"

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
        file_path = os.path.join('./', WORDS_FILE_PATH)
        with open(file_path, 'r') as f:
            for line in f:
                self.validate_word(line.strip())
        
        # print results
        end = time()
        print(f"Puzzle solved in {solve_time_to_string(start, end)}.")
        print(f"{len(self.words) + len(self.pangrams)} words found:")
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
