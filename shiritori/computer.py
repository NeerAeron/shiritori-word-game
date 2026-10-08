"""The computer opponent."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .challenges import ChallengeGame
from .game import Game, Player


@dataclass(frozen=True)
class Difficulty:
    """How the computer plays.

    Word lengths are drawn from a normal distribution and kept within
    ``min_length``..``max_length`` (no upper limit when ``max_length`` is None).
    Longer words score more, so harder opponents reach the target sooner.

    In challenge mode, ``bonus_chance`` is how often the computer goes for the
    bonus challenge, and ``challenge_thinking`` is roughly how many seconds it
    takes to come up with a word.
    """

    name: str
    min_length: int
    max_length: int | None
    mean_length: float
    stdev: float
    bonus_chance: float
    challenge_thinking: float


DIFFICULTIES = {
    difficulty.name: difficulty
    for difficulty in (
        Difficulty(
            "easy", 3, 6, mean_length=4.5, stdev=0.8, bonus_chance=0.1, challenge_thinking=7
        ),
        Difficulty(
            "medium", 6, 11, mean_length=8, stdev=1.3, bonus_chance=0.25, challenge_thinking=5
        ),
        Difficulty(
            "hard", 8, None, mean_length=12, stdev=3, bonus_chance=0.4, challenge_thinking=3.5
        ),
        Difficulty(
            "impossible", 13, None, mean_length=18, stdev=4, bonus_chance=0.6, challenge_thinking=2
        ),
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
    if rng.random() < difficulty.bonus_chance:
        playable = [word for word in playable if game.multiplier_for(word) > 1] or playable
    max_length = difficulty.max_length or float("inf")
    in_range = [word for word in playable if difficulty.min_length <= len(word) <= max_length]
    candidates = in_range or playable
    if not candidates:
        return None

    target = rng.gauss(difficulty.mean_length, difficulty.stdev)
    closest = min(abs(len(word) - target) for word in candidates)
    return rng.choice([word for word in candidates if abs(len(word) - target) == closest])


def thinking_time(game: Game, difficulty: Difficulty, word: str, rng: random.Random) -> float:
    """How many seconds the computer pauses to "think" before typing *word*."""
    if isinstance(game, ChallengeGame):
        mean = difficulty.challenge_thinking
        if game.multiplier_for(word) > 1:
            mean += 2.5  # Finding a word for the bonus as well takes longer.
        return max(1.0, rng.gauss(mean, mean / 4))
    return max(0.2, rng.gauss(0.9, 0.2))


def typing_delays(word: str, rng: random.Random, thinking: float) -> list[float]:
    """Return human-like pauses, in seconds, before each letter of *word* and before Enter.

    *thinking* is added to the pause before the first letter.
    """
    delays = [max(0.05, rng.gauss(0.17, 0.07)) for _ in word]
    delays.append(max(0.05, rng.gauss(0.3, 0.1)))
    delays[0] += thinking
    return delays
