from display_utils import use_main_menu, use_sudoku_menu
from menu_options import MainMenuOptions, SudokuDifficultyOptions
from solvers.SudokuSolver import SudokuSolver

import os

def main() -> int:
    os.system('tput civis')
    option = use_main_menu()
    while option != MainMenuOptions.QUIT:
        res = 0
        if option == MainMenuOptions.SUDOKU:
            res = sudoku()
        
        if res == 1:
            exit_program()
            return 1
        option = use_main_menu()
    return exit_program()

def sudoku() -> int:
    option = use_sudoku_menu()
    if option == SudokuDifficultyOptions.RETURN:
        return 0
    
    solver = SudokuSolver(option)

def exit_program():
    os.system('tput cnorm')
    return 0

if __name__ == "__main__":
    main()
