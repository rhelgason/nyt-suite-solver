from datetime import datetime
from typing import Set

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
        # TODO: scrape puzzle from NYT site
        self.letters = set(["n", "a", "c", "i", "l", "o", "v"])
        self.center = "v"
    
    def solve(self) -> None:
        print(f"Solving today's puzzle:")
        # TODO: write solver algorithm

        print("\nPress ENTER to return to the main menu.")
        input()
