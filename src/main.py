from display_utils import use_main_menu
from menu_options import MainMenuOptions

import os

def main() -> int:
    os.system('tput civis')
    option = use_main_menu()
    print(option)

    return exit_program()

def exit_program():
    os.system('tput cnorm')
    return 0

if __name__ == "__main__":
    main()
