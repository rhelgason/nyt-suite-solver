from game_runner import letter_boxed, spelling_bee, sudoku
from menu_options import MainMenuOptions
from menus import use_main_menu

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
