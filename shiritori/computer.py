"""The computer opponent."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .game import Game, Player


@dataclass(frozen=True)
class Difficulty:
    """How long the computer's words tend to be.

    Word lengths are drawn from a normal distribution and kept within
    ``min_length``..``max_length`` (no upper limit when ``max_length`` is None).
    Longer words score more, so harder opponents reach the target sooner.
    """

    name: str
    min_length: int
    max_length: int | None
    mean_length: float
    stdev: float


DIFFICULTIES = {
    difficulty.name: difficulty
    for difficulty in (
        Difficulty("easy", min_length=3, max_length=6, mean_length=4.5, stdev=0.8),
        Difficulty("medium", min_length=6, max_length=11, mean_length=8, stdev=1.3),
        Difficulty("hard", min_length=8, max_length=None, mean_length=12, stdev=3),
        Difficulty("impossible", min_length=13, max_length=None, mean_length=18, stdev=4),
    )
}


@dataclass
class ComputerPlayer(Player):
    difficulty: Difficulty = DIFFICULTIES["easy"]


def choose_word(game: Game, difficulty: Difficulty, rng: random.Random) -> str | None:
    """Pick a word for the current turn, or return None if nothing can be played."""
    playable = [
        word for word in game.words.starting_with(game.letter) if game.check_word(word) is None
    ]
    max_length = difficulty.max_length or float("inf")
    in_range = [word for word in playable if difficulty.min_length <= len(word) <= max_length]
    candidates = in_range or playable
    if not candidates:
        return None

    target = rng.gauss(difficulty.mean_length, difficulty.stdev)
    closest = min(abs(len(word) - target) for word in candidates)
    return rng.choice([word for word in candidates if abs(len(word) - target) == closest])


def typing_delays(word: str, rng: random.Random) -> list[float]:
    """Return human-like pauses, in seconds, before each letter of *word* and before Enter."""
    delays = [max(0.05, rng.gauss(0.17, 0.07)) for _ in word]
    delays.append(max(0.05, rng.gauss(0.3, 0.1)))
    delays[0] += max(0.2, rng.gauss(0.9, 0.2))  # time to think of the word
    return delays
