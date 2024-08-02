from collections import OrderedDict
from menu_options import MenuOptions
from pynput import keyboard
from typing import Callable, Generic, Optional, Type, TypeVar, Union

import os

VK_NUMPAD_1 = 18

E = TypeVar("E", bound=MenuOptions)

class MenuListener(Generic[E]):
    is_key_already_pressed: bool = False
    selected_idx: int = 0
    menu_options: Type[E] = None
    message: Optional[str] = None

    def __init__(self, menu_options: Type[E], message: str) -> None:
        self.is_key_already_pressed = False
        self.selected_idx = 0
        self.menu_options = menu_options
        self.message = message

    def use_menu(self) -> E:
        self.print_menu()
        with keyboard.Listener(on_press=self.on_press_menu_key, on_release=self.on_release_menu_key, suppress=True) as listener:
            listener.join()
        return self.menu_options.name(self.selected_idx)

    def print_menu(self) -> None:
        os.system('clear')
        print(f"{self.message} Select one of the following options:\n")
        for i, value in enumerate(self.menu_options.list()):
            if i == self.selected_idx:
                print(f">  {i+1}. {value}")
            else:
                print(f"   {i+1}. {value}")
        print()

    def on_press_menu_key(self, key: Union[keyboard.Key, keyboard.KeyCode]) -> Optional[bool]:
        if self.is_key_already_pressed:
            return
        self.is_key_already_pressed = True

        if key == keyboard.Key.down:
            self.selected_idx = (self.selected_idx + 1) % len(self.menu_options)
        elif key == keyboard.Key.up:
            self.selected_idx = (self.selected_idx - 1) % len(self.menu_options)
        elif key == keyboard.Key.enter:
            return False
        elif key == keyboard.Key.esc or key == keyboard.KeyCode.from_char('q'):
            self.selected_idx = len(self.menu_options) - 1
            return False
        elif hasattr(key, 'vk') and key.vk >= VK_NUMPAD_1 and key.vk < VK_NUMPAD_1 + len(self.menu_options):
            self.selected_idx = key.vk - VK_NUMPAD_1
            return False

        self.print_menu()
        return

    def on_release_menu_key(self, key: Union[keyboard.Key, keyboard.KeyCode]) -> bool:
        self.is_key_already_pressed = False
