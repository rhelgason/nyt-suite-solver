from MenuListener import MenuListener
from menu_options import MainMenuOptions, SudokuDifficultyOptions

import os

def clear_terminal():
    os.system('clear')

def use_main_menu():
    main_menu = MenuListener[MainMenuOptions](
        menu_options=MainMenuOptions,
        message="Welcome to the New York Times Suite Solver! " +
        "Select one of the following options:"
    )
    return main_menu.use_menu()

def use_sudoku_menu():
    sudoku_menu = MenuListener[SudokuDifficultyOptions](
        menu_options=SudokuDifficultyOptions,
        message="You have chosen to solve today's Sudoku puzzle! " +
        "Please select a difficulty:"
    )
    return sudoku_menu.use_menu()
