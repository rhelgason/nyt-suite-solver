from display_utils import use_main_menu, use_spelling_bee_menu, use_sudoku_menu
from menu_options import MainMenuOptions, SpellingBeeDateOptions, SudokuDifficultyOptions
from solvers.spelling_bee.SpellingBeeSolver import SpellingBeeSolver
from solvers.sudoku.SudokuSolver import SudokuSolver
import ctypes
import sys
import os 

def main() -> int:
    os.system('tput civis')
    option = use_main_menu()
    while option != MainMenuOptions.QUIT:
        res = 0
        if option == MainMenuOptions.SPELLING_BEE:
            res = spelling_bee()
        elif option == MainMenuOptions.SUDOKU:
            res = sudoku()
        
        if res == 1:
            exit_program()
            return 1
        option = use_main_menu()
    return exit_program()

def spelling_bee() -> int:
    while True:
        option = use_spelling_bee_menu(None)
        if option == SpellingBeeDateOptions.RETURN:
            return 0
        while True:
            option = use_spelling_bee_menu(option)
            if option == SpellingBeeDateOptions.RETURN:
                break
            solver = SpellingBeeSolver(option)
            solver.solve()

def sudoku() -> int:
    while True:
        option = use_sudoku_menu()
        if option == SudokuDifficultyOptions.RETURN:
            return 0
        solver = SudokuSolver(option)
        solver.solve()

def exit_program():
    os.system('tput cnorm')
    return 0

if __name__ == "__main__":
    main()
