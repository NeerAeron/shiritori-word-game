"""The dictionary of playable words."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from importlib import resources


class WordList:
    """A set of lowercase words, indexed by first letter.

    Only words made entirely of the letters a-z are kept; anything else in the
    input (hyphenated compounds, abbreviations, accented words) is dropped.
    """

    def __init__(self, words: Iterable[str]) -> None:
        normalized = (word.strip().lower() for word in words)
        self._words = frozenset(word for word in normalized if word.isascii() and word.isalpha())
        by_letter: dict[str, list[str]] = {}
        for word in sorted(self._words):
            by_letter.setdefault(word[0], []).append(word)
        self._by_letter = {letter: tuple(group) for letter, group in by_letter.items()}

    @classmethod
    def default(cls) -> WordList:
        """Load the English word list that ships with the game."""
        text = resources.files(__package__).joinpath("words.txt").read_text(encoding="utf-8")
        return cls(text.splitlines())

    def __contains__(self, word: object) -> bool:
        return isinstance(word, str) and word.lower() in self._words

    def __iter__(self) -> Iterator[str]:
        return iter(self._words)

    def __len__(self) -> int:
        return len(self._words)

    def starting_with(self, letter: str) -> tuple[str, ...]:
        """Return every word that starts with *letter*, in alphabetical order."""
        return self._by_letter.get(letter.lower(), ())
