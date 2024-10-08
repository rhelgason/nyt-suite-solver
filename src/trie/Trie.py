from trie.Node import END_OF_WORD, Node
from typing import List


"""
Trie data structure for representing all valid words in the
English language. For representing the end of a word, we use
the END_OF_WORD character.
"""
class Trie:
    root: Node = None

    def __init__(self) -> None:
        self.root = Node("", -1)

    def __getitem__(self, key: int) -> str:
        return self.root[key]

    def add_word(self, word: str) -> None:
        self.root = self.add_word_helper(self.root, word + END_OF_WORD)

    def add_word_helper(self, curr: Node, word: str) -> Node:
        # reached end of word
        if len(word) == 0:
            curr.size += 1
            return curr
        
        # recurse to child node
        i = ord(word[0]) - ord('a') + 1
        if curr.children[i] is None:
            curr.children[i] = Node(word[0], curr.depth + 1)
        elif len(word) == 1:
            raise Exception('Word already present in trie.')
        curr.children[i] = self.add_word_helper(curr.children[i], word[1:])
        curr.size += 1
        return curr

    def remove_word(self, word: str) -> None:
        self.root = self.remove_word_helper(self.root, word + END_OF_WORD)

    def remove_word_helper(self, curr: Node, word: str) -> Node:
        # reached end of word
        if len(word) == 0:
            curr.size -= 1
            return None
        
        # recurse to child node
        i = ord(word[0]) - ord('a') + 1
        if curr.children[i] is None:
            raise Exception('Word not present in trie.')
        curr.children[i] = self.remove_word_helper(curr.children[i], word[1:])
        curr.size -= 1

        # if child was deleted, possibly delete curr node
        return curr if any(child is not None for child in curr.children) else None
    
    def contains(self, word: str) -> bool:
        return self.contains_helper(self.root, word + END_OF_WORD)
    
    def contains_helper(self, curr: Node, word: str) -> bool:
        # reached end of word
        if len(word) == 0:
            return True

        # recurse to child node
        i = ord(word[0]) - ord('a') + 1
        if curr.children[i] is None:
            return False
        return self.contains_helper(curr.children[i], word[1:])

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
