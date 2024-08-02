from Box import Box
from Cell import Cell
from typing import List

import math

"""
Represents the entire Sudoku board, which is generally a grid of
9x9 cells. The NYT crossword always uses a 9x9 board, but we support
other sizes (including irregular) for the sake of flexibility.

This solver relies on Donald Knuth's Dancing Links algorithm.
"""
class Grid:
    # basic sudoku structures
    dim: int = 9
    box_height: int = 3
    box_width: int = 3
    rows: List[List[bool]] = []
    cols: List[List[bool]] = []
    divs: List[List[List[bool]]] = []
    board: List[List[Box]] = []

    # dancing links structures
    head: Cell = None
    col_heads: List[Cell] = []

    def __init__(
        self,
        values: List[int] = [],
        box_height: int = 3,
        box_width: int = 3,
    ) -> None:
        self.box_height = box_height
        self.box_width = box_width

        # initialize tracking sets
        self.rows = [[False] * self.dim for _ in range(self.dim)]
        self.cols = [[False] * self.dim for _ in range(self.dim)]
        self.divs = [
            [[False] * self.dim for _ in range(self.box_height)]
            for _ in range(self.box_width)
        ]

        # initialize board
        board = self.reshape_input_board(values)
        self.board = [[None for _ in range(self.dim)] for _ in range(self.dim)]
        for i in range(self.dim):
            for j in range(self.dim):
                if board[i][j] == 0:
                    self.board[i][j] = Box(self.dim)
                else:
                    if self.is_valid():
                        self.board[i][j] = Box(self.dim, board[i][j])
                        self.track_value(i, j, board[i][j])
                    else:
                        raise ValueError(f"Invalid input board at row {i} and column {j}.")

    """
    The input after scraping the NYT website is a list of 81 integers, and
    the board is a 9x9 grid of cells. This function reshapes the input list
    into a 9x9 grid.
    """
    def reshape_input_board(self, values: List[int]) -> List[List[int]]:
        sqrt = math.sqrt(len(values))
        if sqrt != int(sqrt):
            raise ValueError("Input board must be a square.")

        self.dim = int(sqrt)
        board = []
        for i in range(0, dim):
            row = []
            for j in range(0, dim):
                row.append(values[i * dim + j])
            board.append(row)
        return board

    """
    Given a potential placement of a value, check if that value has
    already been placed in the same row, column, or box.
    """
    def is_valid(row: int, col: int, val: int) -> bool:
        return not self.rows[row][val - 1]
        and not self.cols[col][val - 1]
        and not self.divs[row // self.box_height][col // self.box_width][val - 1]
    
    def track_value(row: int, col: int, val: int) -> None:
        self.rows[row][val - 1] = True
        self.cols[col][val - 1] = True
        self.divs[row // self.box_height][col // self.box_width][val - 1] = True
    
    def untrack_value(row: int, col: int, val: int) -> None:
        self.rows[row][val - 1] = False
        self.cols[col][val - 1] = False
        self.divs[row // self.box_height][col // self.box_width][val - 1] = False
