"""The rules of Shiritori: turn order, word validation and scoring."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from .words import WordList

MIN_WORD_LENGTH = 3
DEFAULT_TARGET_SCORE = 100
DEFAULT_TURN_TIME = 10

# Q, X, Y and Z are left out because they make for an awkward first word.
STARTING_LETTERS = "ABCDEFGHIJKLMNOPRSTUVW"


@dataclass
class Player:
    name: str
    score: int = 0


@dataclass(frozen=True)
class Move:
    player: Player
    word: str
    points: int


class Game:
    """A game in progress.

    Players take turns naming a word that starts with the last letter of the
    previous word. A word scores one point per letter, plus a time bonus equal
    to the seconds left on the turn clock; once the clock runs out the bonus
    turns into a penalty. The first player to reach the target score wins.
    """

    def __init__(
        self,
        players: Sequence[Player],
        words: WordList,
        *,
        target_score: int = DEFAULT_TARGET_SCORE,
        turn_time: int = DEFAULT_TURN_TIME,
        rng: random.Random | None = None,
    ) -> None:
        if len(players) < 2:
            raise ValueError("A game needs at least two players.")
        self.players = list(players)
        self.words = words
        self.target_score = target_score
        self.turn_time = turn_time
        self.used_words: set[str] = set()
        self.moves: list[Move] = []
        self._rng = rng or random.Random()
        self._turn = 0
        self.letter = self._rng.choice(STARTING_LETTERS)

    @property
    def current_player(self) -> Player:
        return self.players[self._turn % len(self.players)]

    @property
    def winner(self) -> Player | None:
        """The player who has reached the target score, if anyone has."""
        leader = max(self.players, key=lambda player: player.score)
        return leader if leader.score >= self.target_score else None

    def check_word(self, word: str) -> str | None:
        """Return why *word* can't be played this turn, or None if it can."""
        word = word.lower()
        if len(word) < MIN_WORD_LENGTH:
            return f"use at least {MIN_WORD_LENGTH} letters"
        if not word.startswith(self.letter.lower()):
            return f"must start with {self.letter}"
        if word in self.used_words:
            return "already played"
        if word not in self.words:
            return "not in the dictionary"
        return None

    def score(self, word: str, seconds: float) -> int:
        """Return the points for playing *word* after *seconds* of thinking."""
        return round(len(word) + self.turn_time - seconds)

    def play(self, word: str, seconds: float) -> int:
        """Play *word* for the current player and return the points it scored."""
        problem = self.check_word(word)
        if problem:
            raise ValueError(f"Can't play {word!r}: {problem}.")
        word = word.lower()
        points = self.score(word, seconds)
        self.current_player.score += points
        self.moves.append(Move(self.current_player, word, points))
        self.used_words.add(word)
        self.letter = word[-1].upper()
        self._turn += 1
        return points

    def skip(self) -> None:
        """End the current player's turn without a word; the next player gets a new letter."""
        self.letter = self._rng.choice(STARTING_LETTERS)
        self._turn += 1
