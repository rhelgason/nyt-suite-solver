from display_utils import use_main_menu, use_sudoku_menu
from menu_options import MainMenuOptions, SudokuDifficultyOptions
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
    solver = SpellingBeeSolver()
    solver.solve()
    return 0

def sudoku() -> int:
    option = use_sudoku_menu()
    if option == SudokuDifficultyOptions.RETURN:
        return 0
    
    solver = SudokuSolver(option)
    solver.solve()
    return 0

def exit_program():
    os.system('tput cnorm')
    return 0

if __name__ == "__main__":
    main()
