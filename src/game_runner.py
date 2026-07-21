from datetime import datetime, timedelta
from display_utils import clear_terminal
from menu_options import gen_date_enum, MenuOptions, SpellingBeeDateOptions, SudokuDifficultyOptions
from menus import use_spelling_bee_menu, use_sudoku_menu
from Spinner import Spinner
from solvers.scraping import fetch_game_data
from solvers.letter_boxed.LetterBoxedSolver import LetterBoxedSolver
from solvers.spelling_bee.SpellingBeeSolver import SpellingBeeSolver, BASE_URL as SPELLING_BEE_BASE_URL
from solvers.sudoku.SudokuSolver import SudokuSolver

"""
Interactive orchestration for the terminal UI. This layer wires the pure solver
classes to the pynput-backed menus; the solvers themselves stay headless.
"""

def _wait_for_menu() -> None:
    print("\nPress ENTER to return to the main menu.")
    input()

def letter_boxed() -> int:
    LetterBoxedSolver().solve()
    _wait_for_menu()
    return 0

def _fetch_date_options(option: SpellingBeeDateOptions) -> MenuOptions:
    clear_terminal()
    with Spinner("Fetching dates from NYT website..."):
        data = fetch_game_data(SPELLING_BEE_BASE_URL)['pastPuzzles']
        puzzle_data = None
        if option == SpellingBeeDateOptions.THIS_WEEK:
            puzzle_data = data['thisWeek']
        elif option == SpellingBeeDateOptions.LAST_WEEK:
            puzzle_data = data['lastWeek']
        dates = {}
        if puzzle_data is not None:
            dates = {x['printDate']: x['displayDate'] for x in puzzle_data}
        return gen_date_enum(dates)

def spelling_bee() -> int:
    while True:
        option = use_spelling_bee_menu(None)
        if option == SpellingBeeDateOptions.RETURN:
            return 0
        elif option == SpellingBeeDateOptions.TODAY:
            SpellingBeeSolver().solve()
            _wait_for_menu()
        elif option == SpellingBeeDateOptions.YESTERDAY:
            ds = (datetime.today().date() - timedelta(days=1)).strftime("%Y-%m-%d")
            SpellingBeeSolver(ds).solve()
            _wait_for_menu()
        else:
            DateOptions = _fetch_date_options(option)
            while True:
                date = use_spelling_bee_menu(DateOptions)
                if date == DateOptions.RETURN:
                    break
                SpellingBeeSolver(date._name_).solve()
                _wait_for_menu()

def sudoku() -> int:
    while True:
        option = use_sudoku_menu()
        if option == SudokuDifficultyOptions.RETURN:
            return 0
        SudokuSolver(option).solve()
        _wait_for_menu()
