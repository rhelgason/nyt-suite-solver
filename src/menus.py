from MenuListener import MenuListener
from menu_options import MainMenuOptions, MenuOptions, SpellingBeeDateOptions, SudokuDifficultyOptions
from typing import Optional

"""
Interactive terminal menus. This module (and only this module, via
MenuListener) depends on pynput, so importing the solver classes stays free of
any display/keyboard requirement and can run headlessly.
"""

def use_main_menu():
    main_menu = MenuListener[MainMenuOptions](
        menu_options=MainMenuOptions,
        message="Welcome to the New York Times Suite Solver! " +
        "Select one of the following options:"
    )
    return main_menu.use_menu()

def use_spelling_bee_menu(DateOptions: Optional[MenuOptions] = None) -> MenuOptions:
    if DateOptions == None:
        spelling_bee_menu = MenuListener[SpellingBeeDateOptions](
            menu_options=SpellingBeeDateOptions,
            message="Please select a date for the Spelling Bee puzzle:",
        )
    else:
        spelling_bee_menu = MenuListener[DateOptions](
            menu_options=DateOptions,
            message="Please select a date for the Spelling Bee puzzle:",
        )
    return spelling_bee_menu.use_menu()

def use_sudoku_menu():
    sudoku_menu = MenuListener[SudokuDifficultyOptions](
        menu_options=SudokuDifficultyOptions,
        message="Please select a difficulty for the Sudoku puzzle:"
    )
    return sudoku_menu.use_menu()
