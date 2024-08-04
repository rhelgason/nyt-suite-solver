from MenuListener import MenuListener
from menu_options import define_dynamic_date_enum, MainMenuOptions, SpellingBeeDateOptions, SudokuDifficultyOptions
from time import time
from typing import Optional

import os

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
MAX_PERCENTAGE = 100
NUM_PROGRESS_BAR_DIVISIONS = 20
SECONDS_PER_PROGRESS_BAR_UPDATE = 0.25

last_update = 0

def clear_terminal():
    os.system('clear')

def use_main_menu():
    main_menu = MenuListener[MainMenuOptions](
        menu_options=MainMenuOptions,
        message="Welcome to the New York Times Suite Solver! " +
        "Select one of the following options:"
    )
    return main_menu.use_menu()

def use_spelling_bee_menu(option: Optional[SpellingBeeDateOptions]):
    if option == None:
        spelling_bee_menu = MenuListener[SpellingBeeDateOptions](
            menu_options=SpellingBeeDateOptions,
            message="Please select a date for the Spelling Bee puzzle:",
        )
    else:
        # TODO: use actual dates from API scrape
        DynamicDateEnum = define_dynamic_date_enum(["2024-08-02"])
        spelling_bee_menu = MenuListener[DynamicDateEnum](
            menu_options=DynamicDateEnum,
            message="Please select a date for the Spelling Bee puzzle:",
        )
    return spelling_bee_menu.use_menu()

def use_sudoku_menu():
    sudoku_menu = MenuListener[SudokuDifficultyOptions](
        menu_options=SudokuDifficultyOptions,
        message="Please select a difficulty for the Sudoku puzzle:"
    )
    return sudoku_menu.use_menu()

"""
Takes in a progress percentage between 0 and 100, inclusive,
and runtime info to display a progress bar.
"""
def use_progress_bar(progress: int, start: float, end: float):
    if progress < 0 or progress > MAX_PERCENTAGE:
        raise Exception("Progress percentage must be between 0 and 100.")
    
    loaded = "\u25A0" * (progress // (MAX_PERCENTAGE // NUM_PROGRESS_BAR_DIVISIONS))
    not_loaded = "-" * (NUM_PROGRESS_BAR_DIVISIONS - len(loaded))
    progress_str = f"|{loaded}{not_loaded}|"
    pct_spaces = " " * (len(str(MAX_PERCENTAGE)) - len(str(progress)))
    pct_str = f"{pct_spaces}{progress}%"

    elapsed = int(end - start)
    minutes = elapsed // SECONDS_PER_MINUTE
    seconds = elapsed - (minutes * SECONDS_PER_MINUTE)
    time_str = "[elapsed: " + "{:02d}".format(minutes) + ":" + "{:02d}".format(seconds)

    if progress > 1:
        remaining = int((end - start) * (MAX_PERCENTAGE / progress - 1))
        minutes = remaining // SECONDS_PER_MINUTE
        seconds = remaining - (minutes * SECONDS_PER_MINUTE)
        time_str += ", remaining: " + "{:02d}".format(minutes) + ":" + "{:02d}".format(seconds) + "]"
    else:
        time_str += "]"

    print(f"Progress: {progress_str} {pct_str} {time_str}", end="\r")

def should_update_progress_bar() -> bool:
    global last_update
    curr_time = time()
    if curr_time - last_update > SECONDS_PER_PROGRESS_BAR_UPDATE:
        last_update = curr_time
        return True
    return False

def solve_time_to_string(start: float, end: float) -> str:
    seconds = int(end - start)
    if seconds < SECONDS_PER_MINUTE:
        return f"{seconds:.2f} seconds"
    elif seconds < SECONDS_PER_HOUR:
        minutes = int(seconds // SECONDS_PER_MINUTE)
        seconds = seconds - (minutes * SECONDS_PER_MINUTE)
        return f"{minutes} minutes and {seconds:.2f} seconds"
    else:
        hours = int(seconds // SECONDS_PER_HOUR)
        seconds = seconds - (hours * SECONDS_PER_HOUR)
        minutes = int(seconds // SECONDS_PER_MINUTE)
        seconds = seconds - (minutes * SECONDS_PER_MINUTE)
        return f"{hours} hours, {minutes} minutes, and {seconds:.2f} seconds"
