from trie.Node import Node
from typing import List

END_OF_WORD = '{'

"""
Trie data structure for representing all valid words in the
English language. For representing the end of a word, we use
the END_OF_WORD character.
"""
class Trie:
    root: Node = None
    size: int = 0

    def __init__(self) -> None:
        self.root = Node("", -1)
        self.size = 0

    def add_word(self, word: str) -> None:
        self.root = self.add_word_helper(self.root, word + END_OF_WORD)

    def add_word_helper(self, curr: Node, word: str) -> Node:
        # reached end of word
        if curr.depth == len(word) - 1:
            self.size += 1
            return curr
        
        # recurse to child node
        i = ord(word[curr.depth + 1]) - ord('a')
        if curr.children[i] is None:
            curr.children[i] = Node(word[curr.depth + 1], curr.depth + 1)
        curr.children[i] = self.add_word_helper(curr.children[i], word)
        return curr

    def remove_word(self, word: str) -> None:
        self.root = self.remove_word_helper(self.root, word + END_OF_WORD)

    def remove_word_helper(self, curr: Node, word: str) -> Node:
        # reached end of word
        if curr.depth == len(word) - 1:
            self.size -= 1
            return None
        
        # recurse to child node
        i = ord(word[curr.depth + 1]) - ord('a')
        if curr.children[i] is None:
            raise Exception('Word not present in trie.')
        curr.children[i] = self.remove_word_helper(curr.children[i], word)

        # if child was deleted, possibly delete curr node
        return curr if any(child is not None for child in curr.children) else None

    def to_list(self) -> List[str]:
        res = []
        self.to_list_helper(self.root, "", res)
        return res
    
    def to_list_helper(self, curr: Node, word: str, words: List[str]) -> None:
        if curr.letter == END_OF_WORD:
            words.append(word)
            return
        
        for child in curr.children:
            if child is None:
                continue
            self.to_list_helper(child, word + curr.letter, words)
