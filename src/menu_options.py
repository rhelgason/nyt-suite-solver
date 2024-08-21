from enum import Enum
from typing import Dict

class MenuOptions(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))
    
    @classmethod
    def name(cls, idx):
        val = cls.list()[idx]
        return cls._value2member_map_[val]

class MainMenuOptions(MenuOptions):
    LETTER_BOXED = "Letter Boxed"
    SPELLING_BEE = "Spelling Bee"
    SUDOKU = "Sudoku"
    QUIT = "Quit"

class SpellingBeeDateOptions(MenuOptions):
    TODAY = "Today"
    YESTERDAY = "Yesterday"
    THIS_WEEK = "This Week"
    LAST_WEEK = "Last Week"
    RETURN = "Return"

class SudokuDifficultyOptions(MenuOptions):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"
    RETURN = "Return"

def gen_date_enum(dates: Dict[str, str]) -> MenuOptions:
    dates["RETURN"] = "Return"
    DateOptions = Enum("DateOptions", dates, type=MenuOptions)
    return DateOptions
