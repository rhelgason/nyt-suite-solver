from enum import Enum
from typing import List

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

def gen_date_enum(dates: List[str]) -> MenuOptions:
    dates_dict = {d: d for d in dates}
    dates_dict["RETURN"] = "Return"
    DateOptions = Enum("DateOptions", dates_dict, type=MenuOptions)
    return DateOptions
