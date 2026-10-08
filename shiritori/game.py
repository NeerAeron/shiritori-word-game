"""The rules of Shiritori: turn order, word validation and scoring."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from .words import WordList

MIN_WORD_LENGTH = 3

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
    multiplier: float = 1.0  # The bonus multiplier applied to the points, if any


class Game:
    """A classic game in progress.

    Players take turns naming a word that starts with the last letter of the
    previous word. A word scores one point per letter, plus a time bonus equal
    to the seconds left on the turn clock; once the clock runs out the bonus
    turns into a penalty.

    Once someone reaches the target score, the round is played out so everyone
    has the same number of turns, and the highest score wins. If the lead is
    tied at the end of the round, another round is played.
    """

    mode = "classic"
    default_target_score = 100
    default_turn_time = 10

    def __init__(
        self,
        players: Sequence[Player],
        words: WordList,
        *,
        target_score: int | None = None,
        turn_time: int | None = None,
        rng: random.Random | None = None,
    ) -> None:
        if len(players) < 2:
            raise ValueError("A game needs at least two players.")
        self.players = list(players)
        self.words = words
        self.target_score = target_score or self.default_target_score
        self.turn_time = turn_time or self.default_turn_time
        self.used_words: set[str] = set()
        self.moves: list[Move] = []
        self._rng = rng or random.Random()
        self._turn = 0
        self.letter = self._rng.choice(STARTING_LETTERS)

    @property
    def current_player(self) -> Player:
        return self.players[self._turn % len(self.players)]

    @property
    def round_complete(self) -> bool:
        """Whether every player has had the same number of turns."""
        return self._turn % len(self.players) == 0

    @property
    def final_round(self) -> bool:
        """Whether someone has reached the target, so this round is the last unless it ends tied."""
        return any(player.score >= self.target_score for player in self.players)

    @property
    def winner(self) -> Player | None:
        """The winner, once the game is over."""
        if not (self.round_complete and self.final_round):
            return None
        best = max(player.score for player in self.players)
        leaders = [player for player in self.players if player.score == best]
        return leaders[0] if len(leaders) == 1 else None

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

    def multiplier_for(self, word: str) -> float:
        """Return the bonus multiplier *word* would earn. Classic games have no bonuses."""
        return 1.0

    def score(self, word: str, seconds: float) -> int:
        """Return the points for playing *word* after *seconds* of thinking."""
        return self._score(word, seconds)[0]

    def _score(self, word: str, seconds: float) -> tuple[int, float]:
        points = len(word) + self.turn_time - seconds
        # A bonus multiplies a positive score, but never makes a penalty worse.
        multiplier = self.multiplier_for(word) if points > 0 else 1.0
        return round(points * multiplier), multiplier

    def play(self, word: str, seconds: float) -> int:
        """Play *word* for the current player and return the points it scored."""
        problem = self.check_word(word)
        if problem:
            raise ValueError(f"Can't play {word!r}: {problem}.")
        word = word.lower()
        points, multiplier = self._score(word, seconds)
        self.current_player.score += points
        self.moves.append(Move(self.current_player, word, points, multiplier))
        self.used_words.add(word)
        self.letter = word[-1].upper()
        self._turn += 1
        return points

    def skip(self) -> None:
        """End the current player's turn without a word; the next player gets a new letter."""
        self.letter = self._rng.choice(STARTING_LETTERS)
        self._turn += 1
