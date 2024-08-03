from datetime import datetime
from display_utils import clear_terminal, solve_time_to_string
from menu_options import SudokuDifficultyOptions
from typing import List

import ctypes as ct
import json
import math
import numpy as np
import numpy.typing as npt
import os
import re
import requests
import time

BASE_URL = "https://www.nytimes.com/puzzles/sudoku/"
HTML_DATA_REGEX = r'<script type="text\/javascript">window\.gameData = (.+)<\/script><\/div><div id="portal-editorial-content">'
DANCING_LINKS_PATH = "src/solvers/sudoku/DancingLinks.so"
NYT_DIM = 9
NYT_BOX_WIDTH = 3
NYT_BOX_HEIGHT = 3

"""
Scrapes the NYT Sudoku puzzle and solves it using Donald
Knuth's dancing links algorithm.
"""
class SudokuSolver:
    cdll: ct.CDLL = None
    difficulty: SudokuDifficultyOptions = None
    # TODO: allow solving of archived boards
    ds: datetime = None

    # puzzle attributes
    puzzle: npt.NDArray[npt.NDArray[np.int32]] = None
    dim: int = NYT_DIM
    box_width: int = NYT_BOX_WIDTH
    box_height: int = NYT_BOX_HEIGHT

    def __init__(self, difficulty: SudokuDifficultyOptions) -> None:
        self.cdll = ct.CDLL(os.path.join('./', DANCING_LINKS_PATH))
        self.difficulty = difficulty
        self.ds = datetime.today()
        self.scrape_puzzle()
        return

    def scrape_puzzle(self) -> None:
        fetching_str = f"\nFetching {self.difficulty.value.lower()} puzzle from NYT website..."
        clear_terminal()
        print(fetching_str)

        difficulty_str = self.difficulty.value.lower()
        url = BASE_URL + difficulty_str
        response = requests.get(url)
        match = re.search(HTML_DATA_REGEX, response.text)

        if match:
            data = json.loads(match.group(1))
            puzzle_data = data[difficulty_str]['puzzle_data']['puzzle']
            self.puzzle = self.reshape_input_board(puzzle_data)
            self.dancing_links_init()
            clear_terminal()
            print(fetching_str + " done!")

        else:
            raise Exception("Failed to find game data.")
    
    """
    The input after scraping the NYT website is a list of 81 integers, and
    the board is a 9x9 grid of cells. This function reshapes the input list
    into a 9x9 grid.
    """
    def reshape_input_board(self, values: List[int]) -> npt.NDArray[npt.NDArray[np.int32]]:
        sqrt = math.sqrt(len(values))
        if sqrt != int(sqrt):
            raise ValueError("Input board must be a square.")

        self.dim = int(sqrt)
        board = np.empty([self.dim, self.dim], dtype=np.int32)
        for i in range(0, self.dim):
            for j in range(0, self.dim):
                board[i][j] = values[i * self.dim + j]
                if board[i][j] == 0:
                    board[i][j] = -1
        return board

    def dancing_links_init(self) -> None:
        int_ptr = ct.POINTER(ct.c_int)
        int_ptr_ptr = ct.POINTER(int_ptr)

        _dancing_links_init = self.cdll._dancing_links_init
        _dancing_links_init.argtypes = [int_ptr_ptr, ct.c_int, ct.c_int, ct.c_int]
        _dancing_links_init.restype = ct.c_bool

        ct_arr = np.ctypeslib.as_ctypes(self.puzzle)
        int_ptr_arr = int_ptr * ct_arr._length_
        ct_ptr = ct.cast(int_ptr_arr(*(ct.cast(row, int_ptr) for row in ct_arr)), int_ptr_ptr)
        _dancing_links_init(ct_ptr, self.dim, self.box_height, self.box_width)

    def solve(self) -> None:
        print(f"Solving today's {self.difficulty.value.lower()} puzzle:")
        _dancing_links_solve = self.cdll._dancing_links_solve
        _dancing_links_solve.argtypes = []
        _dancing_links_solve.restype = ct.c_bool
        res = _dancing_links_solve()

        print("\nPress ENTER to return to the main menu.")
        input()
