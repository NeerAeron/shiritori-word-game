"""The computer opponent."""

from __future__ import annotations

import functools
import math
import random
import statistics
import string
from dataclasses import dataclass

from .challenges import ChallengeGame
from .game import Game, Player
from .words import WordList


@dataclass(frozen=True)
class Difficulty:
    """How the computer plays.

    Word lengths are drawn from a normal distribution and kept within
    ``min_length``..``max_length``. Longer words score more.

    ``thinking`` and ``challenge_thinking`` are the average seconds the computer
    takes to come up with a word in classic and challenge mode, and ``spread``
    is how much that varies from turn to turn: the higher it is, the more often
    a quick answer is followed by a long blank, like a newer player. ``typing``
    is the seconds it takes per letter. In challenge mode, ``bonus_chance`` is
    how often it goes for the game bonus, and ``round_bonus_chance`` how often
    it goes for a word that earns plenty of round bonus points. ``tactics`` is
    how strongly it prefers words that end in a letter few words start with.
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
    round_bonus_chance: float = 0
    tactics: float = 0  # How hard it tries to leave the next player an awkward letter


# Word lengths were tuned in simulations against intermediate (beginner) and
# experienced (other levels) players. Harder levels then got quicker thinking
# and tactics, so they're tougher than those original targets.
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
            round_bonus_chance=0.1,
        ),
        Difficulty(
            "easy",
            min_length=5,
            max_length=9,
            mean_length=7,
            stdev=1.2,
            thinking=1.2,
            challenge_thinking=4.8,
            spread=0.8,
            typing=0.25,
            bonus_chance=0.05,
            round_bonus_chance=0.2,
        ),
        Difficulty(
            "medium",
            min_length=7,
            max_length=11,
            mean_length=9,
            stdev=1.3,
            thinking=1.9,
            challenge_thinking=2.8,
            spread=0.8,
            typing=0.22,
            bonus_chance=0.1,
            round_bonus_chance=0.4,
            tactics=0.25,
        ),
        Difficulty(
            "hard",
            min_length=9,
            max_length=15,
            mean_length=12,
            stdev=2,
            thinking=2.3,
            challenge_thinking=2.0,
            spread=0.5,
            typing=0.2,
            bonus_chance=0.2,
            round_bonus_chance=0.6,
            tactics=0.6,
        ),
        Difficulty(
            "impossible",
            min_length=10,
            max_length=16,
            mean_length=13,
            stdev=2,
            thinking=1.9,
            challenge_thinking=1.6,
            spread=0.45,
            typing=0.17,
            bonus_chance=0.7,
            round_bonus_chance=0.8,
            tactics=1.0,
        ),
    )
}


@dataclass
class ComputerPlayer(Player):
    difficulty: Difficulty = DIFFICULTIES["easy"]


# How strongly a letter's ease changes the computer's play (see letter_ease).
EASE_THINKING = 0.2  # Thinking time is multiplied by e^(-0.2 * ease)
EASE_LENGTH = 0.6  # Word length shifts by 0.6 letters per unit of ease


@functools.cache
def _start_counts(words: WordList) -> tuple[dict[str, int], float]:
    counts = {letter: len(words.starting_with(letter)) for letter in string.ascii_lowercase}
    return counts, max(statistics.median(counts.values()), 1)


def letter_ease(words: WordList, letter: str) -> float:
    """How easy it is to think of a word starting with *letter*.

    Zero for an average letter, positive for common ones (S is about 1.1),
    negative for awkward ones (Y is about -2.5). It's the natural log of how
    many words start with the letter compared with the median letter.
    """
    counts, median = _start_counts(words)
    return min(max(math.log(max(counts[letter.lower()], 1) / median), -2.5), 1.2)


def choose_word(game: Game, difficulty: Difficulty, rng: random.Random) -> str | None:
    """Pick a word for the current turn, or return None if nothing can be played.

    Easy starting letters get longer words, awkward ones shorter words. Harder
    computers go for bonuses more often, and favor words that leave the next
    player an awkward letter.
    """
    playable = [
        word for word in game.words.starting_with(game.letter) if game.check_word(word) is None
    ]
    if rng.random() < difficulty.bonus_chance:
        playable = [word for word in playable if game.multiplier_for(word) > 1] or playable
    if not playable:
        return None

    shift = EASE_LENGTH * letter_ease(game.words, game.letter)
    low, high = difficulty.min_length + shift, difficulty.max_length + shift
    candidates = [word for word in playable if low <= len(word) <= high] or playable
    if isinstance(game, ChallengeGame) and rng.random() < difficulty.round_bonus_chance:
        candidates = most_round_points(game, candidates)
    target = rng.gauss(difficulty.mean_length + shift, difficulty.stdev)
    closest = min(abs(len(word) - target) for word in candidates)
    near = [word for word in candidates if abs(len(word) - target) <= closest + 1]
    if not difficulty.tactics:
        return rng.choice(near)
    weights = [math.exp(-difficulty.tactics * letter_ease(game.words, w[-1])) for w in near]
    return rng.choices(near, weights)[0]


def most_round_points(game: Game, words: list[str]) -> list[str]:
    """The words that earn the most round bonus points: about the top quarter of *words*."""
    points = {word: game.round_points(word) for word in words}
    goal = max(sorted(points.values())[len(points) * 3 // 4], 1)
    return [word for word in words if points[word] >= goal] or words


def thinking_time(game: Game, difficulty: Difficulty, word: str, rng: random.Random) -> float:
    """How many seconds the computer pauses to "think" before typing *word*."""
    mean = difficulty.thinking
    if isinstance(game, ChallengeGame):
        mean = difficulty.challenge_thinking
        if game.multiplier_for(word) > 1:
            mean += 3  # Finding a word for the bonus as well takes longer.
    # Awkward letters take longer to think of a word for, common ones less.
    mean *= math.exp(-EASE_THINKING * letter_ease(game.words, game.letter))
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
