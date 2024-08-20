from datetime import datetime, timedelta
from display_utils import clear_terminal, use_sudoku_menu
from menu_options import SudokuDifficultyOptions
from Spinner import Spinner
from time import time
from typing import List

import ctypes as ct
import json
import math
import numpy as np
import numpy.typing as npt
import os
import re
import requests

BASE_URL = "https://www.nytimes.com/puzzles/sudoku/"
HTML_DATA_REGEX = r'<script type="text\/javascript">window\.gameData = (.+)<\/script><\/div><div id="portal-editorial-content">'
DANCING_LINKS_PATH = "src/solvers/sudoku/DancingLinks.so"
OUTPUT_DIRECTORY_PATH = "solutions/sudoku"

NYT_DIM = 9
NYT_BOX_WIDTH = 3
NYT_BOX_HEIGHT = 3

"""
Scrapes the NYT Sudoku puzzle and solves it using Donald
Knuth's dancing links algorithm.
"""
class SudokuSolver:
    cdll: ct.CDLL = None
    puzzle_id: int = None
    difficulty: SudokuDifficultyOptions = None
    ds: str = None

    # puzzle attributes
    puzzle: npt.NDArray[npt.NDArray[np.int32]] = None
    solved_puzzle: npt.NDArray[npt.NDArray[np.int32]] = None
    dim: int = NYT_DIM
    box_width: int = NYT_BOX_WIDTH
    box_height: int = NYT_BOX_HEIGHT

    def __init__(self, difficulty: SudokuDifficultyOptions) -> None:
        self.cdll = ct.CDLL(os.path.join('./', DANCING_LINKS_PATH))
        self.puzzle_id = None
        self.difficulty = difficulty
        self.ds = datetime.today().date().strftime("%Y-%m-%d")
        self.puzzle = None
        self.solved_puzzle = None
        self.dim = NYT_DIM
        self.box_width = NYT_BOX_WIDTH
        self.box_height = NYT_BOX_HEIGHT
        self.scrape_puzzle()
        return

    def scrape_puzzle(self) -> None:
        clear_terminal()
        fetching_str = f"Fetching {self.difficulty.value.lower()} puzzle from NYT website..."
        with Spinner(fetching_str):
            difficulty_str = self.difficulty.value.lower()
            url = BASE_URL + difficulty_str
            response = requests.get(url)
            match = re.search(HTML_DATA_REGEX, response.text)

            if match:
                data = json.loads(match.group(1))
                self.puzzle_id = data[self.difficulty.value.lower()]['puzzle_id']
                puzzle_data = data[difficulty_str]['puzzle_data']['puzzle']
                self.puzzle = self.reshape_input_board(puzzle_data)
                self.dancing_links_init()
            else:
                raise Exception("Failed to find game data.")
        print(fetching_str + " done!")
    
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
        print(f"Solving today's {self.difficulty.value.lower()} puzzle:\n")
        print(self.puzzle_to_string(self.puzzle), "\n")
        _dancing_links_solve = self.cdll._dancing_links_solve
        _dancing_links_solve.argtypes = []
        _dancing_links_solve.restype = ct.c_char_p

        res = ct.create_string_buffer(self.dim * self.dim * 2 - 1)
        start = time()
        _dancing_links_solve(res)
        end = time()

        # print condensed results
        if len(res.value.decode()) != self.dim * self.dim * 2 - 1:
            print("Puzzle could not be solved.")
        else:
            self.solved_puzzle = np.fromstring(res.value.decode(), dtype=int, sep=" ").reshape(self.dim, self.dim)
            if (np.any(self.solved_puzzle)):
                td = timedelta(seconds=end - start) / timedelta(milliseconds=1)
                print("Puzzle has been solved in " + str(td) + " milliseconds:\n")
                print(self.puzzle_to_string(self.solved_puzzle))

        # output results to file
        self.write_solved_puzzle(start, end)
        print("\nPress ENTER to return to the main menu.")
        input()

    def puzzle_to_string(self, puzzle: npt.NDArray[npt.NDArray[np.int32]]) -> str:
        hex_set = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F', '0']
        out = ""
        for i in range (self.dim):
            for j in range (self.dim):
                val = puzzle[i][j]
                out += '.' if val == 0 else hex_set[val - 1]
                if (j != self.dim - 1):
                    out += " "
                else:
                    break
                if ((j + 1) % self.box_width == 0):
                    out += "| "
            if (i != self.dim - 1):
                out += "\n"
            if ((i + 1) % self.box_height == 0 and i + 1 != self.dim):
                for j in range (self.dim):
                    out += '-'
                    if (j != self.dim - 1):
                        out += "-"
                    else:
                        break
                    if ((j + 1) % self.box_width == 0):
                        out += "+-"
                out += "\n"
        return out

    def write_solved_puzzle(self, start: float, end: float) -> None:
        data = {
            "puzzle_id": self.puzzle_id,
            "ds": self.ds,
            "input_puzzle": ','.join(','.join(str(x) for x in y) for y in self.puzzle),
            "solved_puzzle": "",
            "solve_time": str(timedelta(seconds=end - start)),
        }

        if (self.solved_puzzle is not None):
            data['solved_puzzle'] = ','.join(','.join(str(x) for x in y) for y in self.solved_puzzle)

        # set up file path
        output_path = os.path.join('./', OUTPUT_DIRECTORY_PATH)
        if not os.path.exists(output_path):
            os.makedirs(output_path)
        output_file_path = os.path.join(output_path, f"{self.ds}_{self.difficulty.value.lower()}.json")

        with open(output_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

def sudoku() -> int:
    while True:
        option = use_sudoku_menu()
        if option == SudokuDifficultyOptions.RETURN:
            return 0
        solver = SudokuSolver(option)
        solver.solve()
