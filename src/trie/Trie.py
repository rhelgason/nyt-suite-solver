from trie.Node import Node
from typing import List

"""
Trie data structure for representing all valid words in the
English language. For representing the end of a word, we use
the <NEXT ASCII CHARACTER> character.
"""
class Trie:
    root: Node = None
    size: int = 0

    def __init__(self) -> None:
        self.root = Node(None, -1)
        self.size = 0

    def add_word(self, word: str) -> None:
        self.root = self.add_word_helper(self.root, word + '<NEXT ASCII CHARACTER>')

    def add_word_helper(self, curr: Node, word: str) -> Node:
        # reached end of word
        if curr.depth == len(word) - 1:
            self.size += 1
            return curr
        
        # recurse to child node
        i = ord(word[curr.depth + 1]) - ord('a')
        child = curr.children[i]
        if child is None:
            child = Node(word[curr.depth + 1], curr.depth + 1)
        child = self.add_word_helper(child, word)
        return curr

    def remove_word(self, word: str) -> None:
        self.root = self.remove_word_helper(self.root, word + '<NEXT ASCII CHARACTER>')

    def remove_word_helper(self, curr: Node, word: str) -> Node:
        # reached end of word
        if curr.depth == len(word) - 1:
            self.size -= 1
            return None
        
        # recurse to child node
        i = ord(word[curr.depth + 1]) - ord('a')
        child = curr.children[i]
        if child is None:
            raise Exception('Word not present in trie.')
        child = self.remove_word_helper(child, word)

        # if child was deleted, possibly delete curr node
        return curr if any(child is not None for child in curr.children) else None
