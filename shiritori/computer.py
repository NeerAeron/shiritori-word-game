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
    takes to come up with a word in classic and challenge mode, and ``spread``
    is how much that varies from turn to turn: the higher it is, the more often
    a quick answer is followed by a long blank, like a newer player. ``typing``
    is the seconds it takes per letter, and ``bonus_chance`` is how often it
    goes for the bonus challenge in challenge mode.
    """

    name: str
    min_length: int
    max_length: int
    mean_length: float
    stdev: float
    thinking: float
    challenge_thinking: float
    spread: float
    typing: float
    bonus_chance: float


# Tuned in simulations: an intermediate player wins about half their games
# against beginner, and an experienced player wins about 90% / 60% / 30% / 5%
# of classic games against easy / medium / hard / impossible (85% / 50% / 20% /
# 2% in challenge mode, which plays to 150).
DIFFICULTIES = {
    difficulty.name: difficulty
    for difficulty in (
        Difficulty(
            "beginner",
            min_length=3,
            max_length=6,
            mean_length=4.5,
            stdev=0.8,
            thinking=0.8,
            challenge_thinking=3.6,
            spread=0.5,
            typing=0.3,
            bonus_chance=0.05,
        ),
        Difficulty(
            "easy",
            min_length=5,
            max_length=9,
            mean_length=7,
            stdev=1.2,
            thinking=1.3,
            challenge_thinking=5.3,
            spread=0.8,
            typing=0.25,
            bonus_chance=0.05,
        ),
        Difficulty(
            "medium",
            min_length=7,
            max_length=11,
            mean_length=9,
            stdev=1.3,
            thinking=2.5,
            challenge_thinking=3.7,
            spread=0.8,
            typing=0.22,
            bonus_chance=0.1,
        ),
        Difficulty(
            "hard",
            min_length=9,
            max_length=15,
            mean_length=12,
            stdev=2,
            thinking=3.9,
            challenge_thinking=3.4,
            spread=0.5,
            typing=0.2,
            bonus_chance=0.2,
        ),
        Difficulty(
            "impossible",
            min_length=10,
            max_length=16,
            mean_length=13,
            stdev=2,
            thinking=3.8,
            challenge_thinking=3.2,
            spread=0.45,
            typing=0.17,
            bonus_chance=0.7,
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
    spread = difficulty.spread
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
