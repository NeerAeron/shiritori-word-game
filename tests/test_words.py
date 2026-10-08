import string

import pytest

from shiritori.game import MIN_WORD_LENGTH
from shiritori.words import WordList


def test_normalizes_case_and_whitespace():
    words = WordList(["  Apple ", "BANANA\r", "cherry"])
    assert sorted(words) == ["apple", "banana", "cherry"]


@pytest.mark.parametrize("entry", ["x-ray", "e'en", "c.o.d", "café", "two words", ""])
def test_drops_entries_that_are_not_plain_letters(entry):
    assert len(WordList([entry])) == 0


def test_membership_ignores_case():
    words = WordList(["apple"])
    assert "apple" in words
    assert "APPLE" in words
    assert "apples" not in words
    assert 42 not in words


def test_starting_with_returns_sorted_words_for_a_letter():
    words = WordList(["avocado", "apple", "banana", "Apricot"])
    assert words.starting_with("a") == ("apple", "apricot", "avocado")
    assert words.starting_with("A") == ("apple", "apricot", "avocado")
    assert words.starting_with("z") == ()


@pytest.fixture(scope="module")
def default_words():
    return WordList.default()


def test_default_list_is_large(default_words):
    assert len(default_words) > 100_000


def test_default_list_has_only_playable_words(default_words):
    assert all(len(word) >= MIN_WORD_LENGTH for word in default_words)
    assert all(word.isascii() and word.isalpha() and word.islower() for word in default_words)


def test_default_list_has_words_for_every_letter(default_words):
    # Every word ends in a-z, so this guarantees the chain can always continue.
    assert all(default_words.starting_with(letter) for letter in string.ascii_lowercase)
