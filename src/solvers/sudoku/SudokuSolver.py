from datetime import datetime
from display_utils import clear_terminal, solve_time_to_string
from solvers.sudoku.Grid import Grid
from menu_options import SudokuDifficultyOptions

import json
import re
import requests
import time

BASE_URL = "https://www.nytimes.com/puzzles/sudoku/"
HTML_DATA_REGEX = r'<script type="text\/javascript">window\.gameData = (.+)<\/script><\/div><div id="portal-editorial-content">'

"""
Scrapes the NYT Sudoku puzzle and solves it using Donald
Knuth's dancing links algorithm.
"""
class SudokuSolver:
    difficulty: SudokuDifficultyOptions = None
    # TODO: allow solving of archived boards
    ds: datetime = None
    puzzle: Grid = None

    def __init__(self, difficulty: SudokuDifficultyOptions) -> None:
        self.difficulty = difficulty
        self.ds = datetime.today()
        self.scrape_puzzle()
        return

    def scrape_puzzle(self) -> None:
        difficulty_str = self.difficulty.value.lower()
        url = BASE_URL + difficulty_str
        response = requests.get(url)
        match = re.search(HTML_DATA_REGEX, response.text)

        if match:
            data = json.loads(match.group(1))
            puzzle_data = data[difficulty_str]['puzzle_data']['puzzle']
            self.puzzle = Grid(puzzle_data)

        else:
            raise Exception("Failed to find game data.")

    def solve_verbose(self) -> None:
        clear_terminal()
        print(f"\nSolving today's {self.difficulty.value.lower()} Sudoku board:\n")
        print(self.puzzle.to_string())

        start_time = time.time()
        print("\nSolving...")
        if self.solve():
            end_time = time.time()
            print(f"\nSolved in {solve_time_to_string(start_time, end_time)}:\n")
            print(self.puzzle.to_string())
            print("\nPress any key to return to the main menu.")
            input()
        else:
            raise Exception("Failed to solve puzzle.")
    
    def solve(self) -> bool:
        ## TODO: solve the puzzle
        return True
