from typing import Set

"""
Represents a single square in the Sudoku board, which generally
contains 9 cells, each of which can hold a value from 1 to 9.
"""
class Box:
    value: int = -1
    choices: Set[int] = set()

    """
    Although NYT always uses a 9x9 board, we support other sizes
    (including irregular) for the sake of flexibility. The `dim`
    parameter is the number of cells in the box.
    """
    def __init__(
        self,
        dim: int,
        val: int = -1
    ) -> None:
        self.value = val
        if val != -1:
            self.choices = set([val])
        else:
            self.choices = set(range(1, dim + 1))
