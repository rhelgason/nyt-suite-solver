"""
Represents a single cell in the Sudoku board, which generally can hold
a value from 1 to 9. We support a doubly linked list for the dancing
links algorithm.
"""
class Cell:
    # linked list pointers
    left: Cell = None
    right: Cell = None
    up: Cell = None
    down: Cell = None
    col_head: Cell = None

    cand: int = -1
    row: int = -1

    def __init__(
        self,
        left: Cell = self,
        right: Cell = self,
        up: Cell = self,
        down: Cell = self,
        col_head: Cell = self,
        row: int = -1,
    ) -> None:
        self.left = left
        self.right = right
        self.up = up
        self.down = down
        self.col_head = col_head
        self.row = row # MAYBE THIS SHIT

        if (left is self):
            self.cand = -1
        elif (up is self):
            self.cand = 0
        else:
            self.cand = 1
    
    def cover(self) -> None:
        # cover header node
        self.left.right = self.right
        self.right.left = self.left

        # cover related nodes in matrix
        col_curr = self.down
        while col_curr is not self:
            row_curr = col_curr.right
            while row_curr is not col_curr:
                row_curr.up.down = row_curr.down
                row_curr.down.up = row_curr.up
                row_curr.col_head.cand -= 1
                row_curr = row_curr.right
            col_curr = col_curr.down

    def uncover(self) -> None:
        # uncover related nodes in matrix
        col_curr = self.up
        while col_curr is not self:
            row_curr = col_curr.left
            while row_curr is not col_curr:
                row_curr.col_head.cand += 1
                row_curr.up.down = row_curr
                row_curr.down.up = row_curr
                row_curr = row_curr.left
            col_curr = col_curr.up

        # uncover header node
        self.left.right = self
        self.right.left = self
