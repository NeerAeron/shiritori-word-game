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
    ``min_length``..``max_length``. Longer words score more.

    ``thinking`` and ``challenge_thinking`` are the average seconds the computer
    takes to come up with a word in classic and challenge mode; the actual time
    varies from turn to turn, like a person's. ``typing`` is the seconds it
    takes per letter. ``bonus_chance`` is how often it goes for the bonus
    challenge in challenge mode.
    """

    name: str
    min_length: int
    max_length: int
    mean_length: float
    stdev: float
    thinking: float
    challenge_thinking: float
    typing: float
    bonus_chance: float


DIFFICULTIES = {
    difficulty.name: difficulty
    for difficulty in (
        Difficulty(
            "easy",
            3,
            6,
            4.5,
            0.8,
            thinking=2.5,
            challenge_thinking=9.5,
            typing=0.25,
            bonus_chance=0.05,
        ),
        Difficulty(
            "medium", 4, 8, 6, 1, thinking=2.7, challenge_thinking=9, typing=0.25, bonus_chance=0.1
        ),
        Difficulty(
            "hard", 5, 10, 7, 1.5, thinking=2.7, challenge_thinking=8, typing=0.2, bonus_chance=0.2
        ),
        Difficulty(
            "impossible",
            7,
            12,
            9,
            1.5,
            thinking=2.7,
            challenge_thinking=6.5,
            typing=0.18,
            bonus_chance=0.25,
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
    mean = difficulty.thinking
    if isinstance(game, ChallengeGame):
        mean = difficulty.challenge_thinking
        if game.multiplier_for(word) > 1:
            mean += 3  # Finding a word for the bonus as well takes longer.
    # Mostly close to the average, with the occasional long think.
    spread = 0.4
    return max(0.5, mean * rng.lognormvariate(-(spread**2) / 2, spread))


def typing_delays(
    word: str, rng: random.Random, thinking: float, letter_time: float = 0.17
) -> list[float]:
    """Return human-like pauses, in seconds, before each letter of *word* and before Enter.

    *thinking* is added to the pause before the first letter, and each letter
    takes *letter_time* seconds on average.
    """
    delays = [max(0.05, rng.gauss(letter_time, letter_time / 2.5)) for _ in word]
    delays.append(max(0.05, rng.gauss(0.3, 0.1)))
    delays[0] += thinking
    return delays
