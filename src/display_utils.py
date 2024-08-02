from MenuListener import MenuListener
from menu_options import MainMenuOptions, SudokuDifficultyOptions

import os

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600

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

def solve_time_to_string(start: float, end: float) -> str:
    seconds = end - start
    if seconds < SECONDS_PER_MINUTE:
        return f"{seconds:.2f} seconds"
    elif seconds < SECONDS_PER_HOUR:
        minutes = seconds // SECONDS_PER_MINUTE
        seconds = seconds - (minutes * SECONDS_PER_MINUTE)
        return f"{minutes} minutes and {seconds:.2f} seconds"
    else:
        hours = seconds // SECONDS_PER_HOUR
        seconds = seconds - (hours * SECONDS_PER_HOUR)
        minutes = seconds // SECONDS_PER_MINUTE
        seconds = seconds - (minutes * SECONDS_PER_MINUTE)
        return f"{hours} hours, {minutes} minutes, and {seconds:.2f} seconds"
