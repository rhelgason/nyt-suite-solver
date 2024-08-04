from datetime import datetime
from display_utils import clear_terminal
from typing import Set

NUM_LETTERS = 7

"""
Scrapes the NYT Spelling Bee puzzle and solves it using
a trie data structure.
"""
class SpellingBeeSolver:
    # TODO: allow solving of archived boards
    ds: datetime = None

    # puzzle attributes
    letters: Set[str] = set()
    center: str = None

    def __init__(self) -> None:
        self.ds = datetime.today()
        self.scrape_puzzle()
        return
    
    def scrape_puzzle(self) -> None:
        fetching_str = f"Fetching puzzle from NYT website..."
        clear_terminal()
        print(fetching_str)

        # TODO: scrape puzzle from NYT site
        self.letters = set(["n", "a", "c", "i", "l", "o", "v"])
        self.center = "v"

        clear_terminal()
        print(fetching_str + " done!")
    
    def puzzle_to_string(self) -> str:
        if len(self.letters) != NUM_LETTERS:
            raise Exception("Incorrect number of letters in puzzle.")
        self.letters.remove(self.center)
        letters = list(self.letters)
        letters = [x.upper() for x in letters]
        
        res = f"""
                 _____
                /     \\
          _____/   {letters[0]}   \\_____
         /     \\       /     \\
        /   {letters[1]}   \\_____/   {letters[2]}   \\
        \       /     \\       /
         \_____/   {self.center.upper()}   \\_____/
         /     \\       /     \\
        /   {letters[3]}   \\_____/   {letters[4]}   \\
        \       /     \\       /
         \_____/   {letters[5]}   \\_____/
               \       /
                \_____/
        """
        self.letters.add(self.center)
        return res
    
    def solve(self) -> None:
        print(f"Solving today's puzzle:")
        print(self.puzzle_to_string())

        # TODO: write solver algorithm
        print("\nPress ENTER to return to the main menu.")
        input()
