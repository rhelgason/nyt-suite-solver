from display_utils import use_main_menu
from menu_options import MainMenuOptions
from solvers.letter_boxed.LetterBoxedSolver import letter_boxed
from solvers.spelling_bee.SpellingBeeSolver import spelling_bee
from solvers.sudoku.SudokuSolver import sudoku

import os

def main() -> int:
    os.system('tput civis')
    option = use_main_menu()
    while option != MainMenuOptions.QUIT:
        res = 0
        if option == MainMenuOptions.LETTER_BOXED:
            res = letter_boxed()
        elif option == MainMenuOptions.SPELLING_BEE:
            res = spelling_bee()
        elif option == MainMenuOptions.SUDOKU:
            res = sudoku()
        
        if res == 1:
            exit_program()
            return 1
        option = use_main_menu()
    return exit_program()

def exit_program():
    os.system('tput cnorm')
    return 0

if __name__ == "__main__":
    main()
