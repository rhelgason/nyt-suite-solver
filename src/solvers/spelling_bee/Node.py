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
    children: List[GenericNode] = []

    def __init__(self, letter: str, depth: int) -> None:
        self.letter = letter
        self.depth = depth
        self.children = []

    def set_child(self, idx: int, child: GenericNode) -> None:
        self.children[idx] = child
    
    def add_child(self, child: GenericNode) -> None:
        self.children[] = child
