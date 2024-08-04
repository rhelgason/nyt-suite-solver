from enum import Enum

class MenuOptions(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))
    
    @classmethod
    def name(cls, idx):
        val = cls.list()[idx]
        return cls._value2member_map_[val]

class MainMenuOptions(MenuOptions):
    SPELLING_BEE = "Spelling Bee"
    SUDOKU = "Sudoku"
    QUIT = "Quit"

class SudokuDifficultyOptions(MenuOptions):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"
    RETURN = "Return"
