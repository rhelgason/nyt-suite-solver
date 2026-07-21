from trie.Node import END_OF_WORD
from trie.Trie import Trie


def build(words):
    t = Trie()
    for w in words:
        t.add_word(w)
    return t


def test_add_and_contains():
    t = build(["cat", "car", "dog"])
    assert t.contains("cat")
    assert t.contains("car")
    assert t.contains("dog")
    # prefixes and extensions of stored words are not themselves members
    assert not t.contains("ca")
    assert not t.contains("cats")


def test_to_list_returns_all_words_without_sentinel():
    words = ["cat", "car", "dog", "do"]
    t = build(words)
    assert sorted(t.to_list()) == sorted(words)
    assert all(END_OF_WORD not in w for w in t.to_list())


def test_duplicate_add_is_idempotent():
    t = build(["cat"])
    t.add_word("cat")  # must not raise or double-count
    assert t.to_list() == ["cat"]
    assert t.root.size == 1


def test_getitem_indexes_every_word_exactly_once():
    words = ["cat", "car", "dog", "do", "an", "ant"]
    t = build(words)
    indexed = [t[i] for i in range(t.root.size)]
    assert sorted(indexed) == sorted(words)


def test_remove_word():
    t = build(["cat", "car"])
    t.remove_word("cat")
    assert not t.contains("cat")
    assert t.contains("car")
    assert t.to_list() == ["car"]
