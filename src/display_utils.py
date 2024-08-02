from MenuListener import MenuListener
from menu_options import MainMenuOptions

import os

def clear_terminal():
    os.system('clear')

def use_main_menu():
    main_menu = MenuListener[MainMenuOptions](
        menu_options=MainMenuOptions,
        message="Welcome to the New York Times Suite Solver!"
    )
    return main_menu.use_menu()
