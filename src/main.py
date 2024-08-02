from display_utils import use_main_menu, use_sudoku_menu
from menu_options import MainMenuOptions, SudokuDifficultyOptions
from solvers.sudoku.SudokuSolver import SudokuSolver
import ctypes
import sys
import os 

dir_path = os.path.dirname(os.path.realpath(__file__))
handle = ctypes.CDLL(dir_path + "/solvers/sudoku/libTest.so")     

handle.My_Function.argtypes = [ctypes.c_int]

def main() -> int:
    os.system('tput civis')
    return handle.My_Function(23)

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
    solver.solve_verbose()

def exit_program():
    os.system('tput cnorm')
    return 0

if __name__ == "__main__":
    main()
