from datetime import datetime, timedelta
from display_utils import clear_terminal, MAX_PERCENTAGE, should_update_progress_bar, use_progress_bar, use_spelling_bee_menu
from enum import Enum
from menu_options import gen_date_enum, MenuOptions, SpellingBeeDateOptions
from Spinner import Spinner
from time import time
from trie.Trie import Trie
from typing import Any, Dict, List, Set

import json
import os
import re
import requests

BASE_URL = "https://www.nytimes.com/puzzles/spelling-bee"
HTML_DATA_REGEX = r'<script type="text\/javascript">window\.gameData = (.+)<\/script><\/div><div id="portal-editorial-content">'

WORDS_FILE_PATH = "wordlist.txt"
OUTPUT_DIRECTORY_PATH = "solutions/spelling_bee"
NUM_LETTERS = 7
MIN_LENGTH = 4

# defines ranks by percentage of completion
class SpellingBeeRanks(Enum):
    QUEEN_BEE = 100
    GENIUS = 70
    AMAZING = 50
    GREAT = 40
    NICE = 25
    SOLID = 15
    GOOD = 8
    MOVING_UP = 5
    GOOD_START = 2
    BEGINNER = 0

"""
Scrapes the NYT Spelling Bee puzzle and solves it, all backed
by a trie data structure.
"""
class SpellingBeeSolver:
    puzzle_id: int = None
    answers: Trie = []
    ds: str = None

    letters: Set[str] = set()
    center: str = None
    words: Trie = []
    pangrams: Trie = []

    def __init__(self, ds: str = None) -> None:
        self.answers = Trie()
        self.ds = ds or datetime.today().date().strftime("%Y-%m-%d")
        self.letters = set()
        self.center = None
        self.words = Trie()
        self.pangrams = Trie()
        self.scrape_puzzle()
        return

    @staticmethod
    def use_date_options(option: SpellingBeeDateOptions) -> MenuOptions:
        clear_terminal()
        with Spinner("Fetching dates from NYT website..."):
            response = requests.get(BASE_URL)
            match = re.search(HTML_DATA_REGEX, response.text)
            if not match:
                raise Exception("Failed to find game data.")
            data = json.loads(match.group(1))['pastPuzzles']
            puzzle_data = None
            if option == SpellingBeeDateOptions.THIS_WEEK:
                puzzle_data = data['thisWeek']
            elif option == SpellingBeeDateOptions.LAST_WEEK:
                puzzle_data = data['lastWeek']

            dates = []
            if puzzle_data != None:
                dates = {x['printDate']: x['displayDate'] for x in puzzle_data}
            return gen_date_enum(dates)
    
    def scrape_puzzle(self) -> None:
        fetching_str = f"Fetching puzzle from NYT website..."
        clear_terminal()
        with Spinner(fetching_str):
            response = requests.get(os.path.join(BASE_URL, self.ds))
            match = re.search(HTML_DATA_REGEX, response.text)
            if match:
                data = json.loads(match.group(1))
                puzzle_data = data['today']
                self.puzzle_id = puzzle_data['id']
                self.center = puzzle_data['centerLetter']
                self.letters = set(puzzle_data['validLetters'])
                for answer in puzzle_data['answers']:
                    self.answers.add_word(answer)
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
        date = datetime.strptime(self.ds, "%Y-%m-%d")
        print(f"Solving puzzle for {date.strftime('%B %d, %Y')}:")
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
        end = time()
        use_progress_bar(MAX_PERCENTAGE, start, end)

        # print condensed results
        words = self.words.to_list()
        pangrams = self.pangrams.to_list()
        words.sort(key=lambda x: (-len(x), x))
        pangrams.sort(key=lambda x: (-len(x), x))

        print(f"\n\n{len(words) + len(pangrams)} possible words found:")
        print(f"\t- Pangrams: " + ', '.join(pangrams))
        low = 0
        for i, word in enumerate(words):
            if len(word) < len(words[low]):
                print(f"\t- {len(words[low])}-letter words: " + ', '.join(words[low:i]))
                low = i

        # output results to file
        self.write_solved_puzzle(start, end)
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

        if len(used_letters) == NUM_LETTERS:
            self.pangrams.add_word(word)
        else:
            self.words.add_word(word)
    
    def write_solved_puzzle(self, start: float, end: float) -> None:
        # set up output data
        words = self.words.to_list()
        pangrams = self.pangrams.to_list()
        answers = self.answers.to_list()
        all_words = words + pangrams

        data = {
            "puzzle_id": self.puzzle_id,
            "ds": self.ds,
            "center": self.center,
            "letters": list(self.letters),
            "pangrams": pangrams,
            "valid_answers": list(set(all_words) - (set(all_words) - set(answers))),
            "invalid_answers": list(set(all_words) - set(answers)),
            "missed_answers": list(set(answers) - set(all_words)),
            "solve_time": str(timedelta(seconds=end - start))[:-3],
        }
        self.write_performance(data)

        # set up file path
        output_path = os.path.join('./', OUTPUT_DIRECTORY_PATH)
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_file_path = os.path.join(output_path, f"{self.ds}.json")

        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def write_performance(self, data: Dict[str, Any]) -> None:
        score = 0
        for answer in data['valid_answers']:
            score += self.score_word(answer)
        data['score'] = score

        missed_score = 0
        for answer in data['missed_answers']:
            missed_score += self.score_word(answer)
        percentage = score / (score + missed_score) * 100
        data['percentage'] = percentage

        ranks = list(map(lambda c: c.value, SpellingBeeRanks))
        for i, value in enumerate(ranks):
            if percentage >= value:
                data['rank'] = SpellingBeeRanks._value2member_map_[value]._name_
                return
    
    def score_word(self, word: str) -> int:
        score = len(word) - MIN_LENGTH + 1
        if self.pangrams.contains(word):
            score += 7
        return score

def spelling_bee() -> int:
    while True:
        option = use_spelling_bee_menu(None)
        if option == SpellingBeeDateOptions.RETURN:
            return 0
        elif option == SpellingBeeDateOptions.TODAY:
            solver = SpellingBeeSolver()
            solver.solve()
        elif option == SpellingBeeDateOptions.YESTERDAY:
            ds = (datetime.today().date() - timedelta(days=1)).strftime("%Y-%m-%d")
            solver = SpellingBeeSolver(ds)
            solver.solve()
        else:
            DateOptions = SpellingBeeSolver.use_date_options(option)
            while True:
                date = use_spelling_bee_menu(DateOptions)
                if date == DateOptions.RETURN:
                    break
                solver = SpellingBeeSolver(date._name_)
                solver.solve()
