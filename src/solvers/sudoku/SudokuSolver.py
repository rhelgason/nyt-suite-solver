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
    difficulty: SudokuDifficultyOptions = None
    # TODO: allow solving of archived boards
    ds: datetime = None

    # puzzle attributes
    puzzle: npt.NDArray[npt.NDArray[np.int16]] = None
    dim: int = NYT_DIM
    box_width: int = NYT_BOX_WIDTH
    box_height: int = NYT_BOX_HEIGHT

    def __init__(self, difficulty: SudokuDifficultyOptions) -> None:
        self.difficulty = difficulty
        self.ds = datetime.today()
        self.scrape_puzzle()
        return

    def scrape_puzzle(self) -> None:
        clear_terminal()
        print("\nFetching puzzle from NYT website...")

        difficulty_str = self.difficulty.value.lower()
        url = BASE_URL + difficulty_str
        response = requests.get(url)
        match = re.search(HTML_DATA_REGEX, response.text)

        if match:
            data = json.loads(match.group(1))
            puzzle_data = data[difficulty_str]['puzzle_data']['puzzle']
            self.puzzle = self.reshape_input_board(puzzle_data)

        else:
            raise Exception("Failed to find game data.")
    
    """
    The input after scraping the NYT website is a list of 81 integers, and
    the board is a 9x9 grid of cells. This function reshapes the input list
    into a 9x9 grid.
    """
    def reshape_input_board(self, values: List[int], ) -> npt.NDArray[npt.NDArray[np.int16]]:
        sqrt = math.sqrt(len(values))
        if sqrt != int(sqrt):
            raise ValueError("Input board must be a square.")

        self.dim = int(sqrt)
        board = np.empty([self.dim, self.dim], dtype=np.int16)
        for i in range(0, self.dim):
            for j in range(0, self.dim):
                board[i][j] = values[i * self.dim + j]
        return board
    
    """
    The NYT crossword always uses a 9x9 board, but this method will use hex
    characters to support up to 16x16 boards.
    """
    def puzzle_to_string(self) -> str:
        # print each row
        res = ""
        for i in range(self.dim):
            for j in range(self.dim):
                res += "." if self.puzzle[i][j] == -1 else ('%x' % self.puzzle[i][j])
                if j != self.dim - 1:
                    res += " "
                else:
                    break
                if (j + 1) % self.box_width == 0:
                    res += "| "

            if i != self.dim - 1:
                res += "\n"

            if (i + 1) % self.box_height == 0 and i != self.dim - 1:
                for j in range(self.dim):
                    res += "-"
                    if j != self.dim - 1:
                        res += "-"
                    else:
                        break
                    if (j + 1) % self.box_width == 0:
                        res += "+-"
                res += "\n"
        return res

    def solve_verbose(self) -> None:
        print(f"Solving today's {self.difficulty.value.lower()} Sudoku board:\n")
        print(self.puzzle_to_string())

        start_time = time.time()
        print("\nSolving...")
        if self.solve():
            end_time = time.time()
            print(f"\nSolved in {solve_time_to_string(start_time, end_time)}:\n")
            """
            print(self.puzzle.to_string())
            """
            print("\nPress any key to return to the main menu.")
            input()
        else:
            raise Exception("Failed to solve puzzle.")

    def solve(self) -> bool:
        #cdll = ctypes.CDLL(os.path.join('./', DANCING_LINKS_PATH))
        #_dancing_links_main = cdll._dancing_links_main
        #_dancing_links_main.argtypes = (ctypes.POINTER(ctypes.POINTER(ctypes.c_int * GRID_HEIGHT) * GRID_WIDTH), ctypes.c_int)
        #_dancing_links_main.restype = ctypes.c_bool

        UI16Ptr = ct.POINTER(ct.c_int)
        UI16PtrPtr = ct.POINTER(UI16Ptr)

        dll00 = ct.CDLL(os.path.join('./', DANCING_LINKS_PATH))
        dll00Func00 = dll00._dancing_links_main
        dll00Func00.argtypes = [UI16PtrPtr]
        dll00Func00.restype = ct.c_uint

        dim0 = GRID_HEIGHT
        dim1 = GRID_WIDTH

        # The "magic" happens in the following lines of code
        ct_arr = np.ctypeslib.as_ctypes(np_arr_2d)
        UI16PtrArr = UI16Ptr * ct_arr._length_
        ct_ptr = ct.cast(UI16PtrArr(*(ct.cast(row, UI16Ptr) for row in ct_arr)), UI16PtrPtr)
        res = dll00Func00(ct_ptr, GRID_HEIGHT)

        print("\n{0:s} returned: {1:d}".format(dll00Func00.__name__, res))
