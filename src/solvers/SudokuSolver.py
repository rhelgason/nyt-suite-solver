from datetime import datetime
from menu_options import SudokuDifficultyOptions

import json
import re
import requests

BASE_URL = "https://www.nytimes.com/puzzles/sudoku/"
HTML_DATA_REGEX = r'<script type="text\/javascript">window\.gameData = (.+)<\/script><\/div><div id="portal-editorial-content">'

"""
Scrapes the NYT Sudoku puzzle and solves it using Donald
Knuth's dancing links algorithm.
"""
class SudokuSolver:
    def __init__(self, difficulty: SudokuDifficultyOptions) -> None:
        self.scrape_puzzle(difficulty, datetime.today())
        return

    def scrape_puzzle(self, difficulty: SudokuDifficultyOptions, ds: datetime) -> None:
        difficulty_str = difficulty.value.lower()
        url = BASE_URL + difficulty_str
        response = requests.get(url)
        match = re.search(HTML_DATA_REGEX, response.text)

        if match:
            data = json.loads(match.group(1))
            puzzle = data[difficulty_str]['puzzle_data']['puzzle']

        else:
            raise Exception("Failed to find game data.")
