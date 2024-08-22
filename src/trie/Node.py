from typing import List, Optional

END_OF_WORD = '`'

# generic parent class for typing the recursive Node structure
class GenericNode:
    def __init__(self) -> None:
        pass

"""
Represents a single node in our trie data structure. Each node
contains a single letter with children leading to complete
English words.
"""
class Node(GenericNode):
    letter: str = None
    depth: int = -1
    size: int = 0
    children: List[Optional[GenericNode]] = []

    def __init__(self, letter: str, depth: int) -> None:
        self.letter = letter
        self.depth = depth
        self.size = 0
        # NOTE: we add an additional child for signalling end of word
        self.children = [None] * (ord('z') - ord('a') + 2)

    def __getitem__(self, key: int) -> str:
        if key >= self.size:
            raise IndexError("Index out of range.")
        if (key == 0 and self.letter == END_OF_WORD):
            return ""
        
        curr_size = 0
        for i, child in enumerate(self.children):
            if child is None:
                continue
            curr_size += child.size
            if curr_size > key:
                return self.letter + child[key - (curr_size - child.size)]

    def set_child(self, idx: int, child: GenericNode) -> None:
        self.children[idx] = child
    
    def add_child(self, child: GenericNode) -> None:
        self.children.append(child)
