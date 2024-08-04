from solvers.spelling_bee.Node import Node

SPELLING_BEE_MIN_LENGTH = 4

"""
Trie data structure for representing all possible words in the
English language.
"""
class Trie:
    root: Node = None
    size: int = 0
    min_length: int = SPELLING_BEE_MIN_LENGTH

    def __init__(self, min_length = SPELLING_BEE_MIN_LENGTH) -> None:
        self.min_length = min_length
