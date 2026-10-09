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
    multiplier: float = 1.0  # The game bonus multiplier applied to the points, if any
    time_bonus: int = 0  # Points for time left on the clock (negative once it ran out)
    round_bonus: int = 0  # Points from the turn's round bonus


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
        """Return the game bonus multiplier *word* would earn. Classic games have no bonuses."""
        return 1.0

    def round_points(self, word: str) -> int:
        """Return the round bonus points *word* would earn. Classic games have no bonuses."""
        return 0

    def time_points(self, seconds: float) -> int:
        """Return the points for answering after *seconds*: one per second left, or lost after."""
        return round(self.turn_time - seconds)

    def score(self, word: str, seconds: float) -> int:
        """Return the points for playing *word* after *seconds* of thinking."""
        return self._move(word.lower(), seconds).points

    def _move(self, word: str, seconds: float) -> Move:
        """Score *word* for the current player: letters, round bonus, and time points."""
        time_bonus = self.time_points(seconds)
        round_bonus = self.round_points(word)
        points = len(word) + round_bonus + time_bonus
        # The game bonus multiplies a positive score, but never makes a penalty worse.
        multiplier = self.multiplier_for(word) if points > 0 else 1.0
        points = round(points * multiplier)
        return Move(self.current_player, word, points, multiplier, time_bonus, round_bonus)

    def play(self, word: str, seconds: float) -> int:
        """Play *word* for the current player and return the points it scored."""
        problem = self.check_word(word)
        if problem:
            raise ValueError(f"Can't play {word!r}: {problem}.")
        move = self._move(word.lower(), seconds)
        self.current_player.score += move.points
        self.moves.append(move)
        self.used_words.add(move.word)
        self.letter = move.word[-1].upper()
        self._turn += 1
        return move.points

    def skip(self) -> None:
        """End the current player's turn without a word; the next player gets a new letter."""
        self.letter = self._rng.choice(STARTING_LETTERS)
        self._turn += 1
