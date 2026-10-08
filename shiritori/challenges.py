"""Challenge mode: a new spelling challenge every turn, and a bonus challenge for the whole game.

Every word must meet the turn's challenge. Words that also meet the game's
bonus challenge have their points multiplied. Vowels are A, E, I, O and U;
Y counts as a consonant. No challenge depends on word length or time.
"""

from __future__ import annotations

import math
import random
from collections import Counter, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from .game import DEFAULT_TARGET_SCORE, MIN_WORD_LENGTH, Game, Player
from .words import WordList

VOWELS = frozenset("aeiou")


@dataclass(frozen=True)
class Challenge:
    text: str
    test: Callable[[str], bool]


def _ends_with(ending: str) -> Challenge:
    return Challenge(f"end with {ending.upper()}", lambda word: word.endswith(ending))


def _includes(letters: str) -> Challenge:
    return Challenge(f"include {letters.upper()}", lambda word: letters in word)


def _without(*letters: str) -> Challenge:
    names = " or ".join(letter.upper() for letter in letters)
    return Challenge(
        f"no letter {names}", lambda word: not any(letter in word for letter in letters)
    )


def _second_letter(letter: str) -> Challenge:
    return Challenge(f"second letter is {letter.upper()}", lambda word: word[1] == letter)


def _hides(description: str, *hidden: str) -> Challenge:
    listed = ", ".join(word.upper() for word in hidden)
    return Challenge(f"hide {description} ({listed})", lambda word: any(h in word for h in hidden))


def _vowel_count(word: str) -> int:
    return sum(letter in VOWELS for letter in word)


def _has_run(word: str, length: int, *, vowels: bool) -> bool:
    """Whether *word* has *length* vowels (or consonants) in a row."""
    run = 0
    for letter in word:
        run = run + 1 if (letter in VOWELS) == vowels else 0
        if run >= length:
            return True
    return False


def _double_letters(word: str) -> set[str]:
    return {a for a, b in pairwise(word) if a == b}


def _only_vowel(vowel: str) -> Challenge:
    return Challenge(
        f"{vowel.upper()} is the only vowel", lambda word: set(word) & VOWELS == {vowel}
    )


EASY = (
    *(_ends_with(letter) for letter in "seydtrn"),
    Challenge("end with a vowel", lambda word: word[-1] in VOWELS),
    *(_ends_with(ending) for ending in ("ed", "er", "ing", "es")),
    Challenge("include a double letter", lambda word: bool(_double_letters(word))),
    *(_without(letter) for letter in "astrion"),
    Challenge("two vowels in a row", lambda word: _has_run(word, 2, vowels=True)),
    Challenge("second letter is a vowel", lambda word: word[1] in VOWELS),
    Challenge("second letter is a consonant", lambda word: word[1] not in VOWELS),
    Challenge("third letter is a vowel", lambda word: word[2] in VOWELS),
    *(_includes(letter) for letter in "mpbhcu"),
    Challenge("exactly one vowel", lambda word: _vowel_count(word) == 1),
    Challenge("exactly two vowels", lambda word: _vowel_count(word) == 2),
    Challenge("use only one kind of vowel", lambda word: len(set(word) & VOWELS) == 1),
    Challenge("no letter used twice", lambda word: len(set(word)) == len(word)),
    _includes("er"),
    _includes("in"),
)

MEDIUM = (
    _without("e"),
    *(_ends_with(letter) for letter in "lagkhop"),
    *(_ends_with(ending) for ending in ("ly", "al", "ion", "ic")),
    Challenge("end with the letter you start with", lambda word: word[-1] == word[0]),
    Challenge("end with a double letter", lambda word: word[-1] == word[-2]),
    *(_includes(letter) for letter in "yfkwvg"),
    *(_includes(pair) for pair in ("th", "sh", "ch", "ou", "ea", "ll", "ss", "st", "ie")),
    *(_includes(pair) for pair in ("oo", "ee", "ow")),
    Challenge("use the first letter again", lambda word: word[0] in word[1:]),
    Challenge("three consonants in a row", lambda word: _has_run(word, 3, vowels=False)),
    Challenge(
        "alternate consonants and vowels",
        lambda word: all((a in VOWELS) != (b in VOWELS) for a, b in pairwise(word)),
    ),
    *(_second_letter(letter) for letter in "rlh"),
    _hides("an animal", "ant", "bat", "cat", "cow", "dog", "hen", "owl", "pig", "rat"),
    _hides("a body part", "arm", "ear", "eye", "hip", "leg", "lip", "rib", "toe"),
    Challenge("hide the word ATE", lambda word: "ate" in word),
)

HARD = (
    *(_includes(letter) for letter in "zxj"),
    *(_includes(pair) for pair in ("qu", "ph", "ck", "gh", "tt")),
    *(_ends_with(ending) for ending in ("ness", "ous", "ity", "ate", "est", "ist")),
    Challenge("use one letter three times", lambda word: max(Counter(word).values()) >= 3),
    _without("a", "e"),
    _without("e", "i"),
    Challenge("four consonants in a row", lambda word: _has_run(word, 4, vowels=False)),
    _hides("a color", "red", "tan", "blue", "pink", "gold"),
    _hides("a number", "one", "two", "six", "ten"),
    *(
        Challenge(f"hide the word {hidden.upper()}", lambda word, h=hidden: h in word)
        for hidden in ("and", "all", "man")
    ),
)

TURN_CHALLENGES = {"easy": EASY, "medium": MEDIUM, "hard": HARD}

# How often each tier comes up. Easy challenges are the most common.
TIER_WEIGHTS = {"easy": 0.5, "medium": 0.35, "hard": 0.15}

# Bonus challenges by their base multiplier: harder ones pay more.
BONUS_CHALLENGES = {
    1.5: (
        Challenge("include J, Q, X, or Z", lambda word: bool(set(word) & set("jqxz"))),
        Challenge(
            "use the same vowel three times",
            lambda word: any(word.count(vowel) >= 3 for vowel in VOWELS),
        ),
        Challenge("no A, E, or I", lambda word: not set(word) & set("aei")),
        Challenge("no E, I, or O", lambda word: not set(word) & set("eio")),
    ),
    2.0: (
        Challenge("more vowels than consonants", lambda word: 2 * _vowel_count(word) > len(word)),
        _only_vowel("a"),
        _only_vowel("e"),
        _only_vowel("u"),
        Challenge(
            "a double letter and end with Y",
            lambda word: bool(_double_letters(word)) and word.endswith("y"),
        ),
        Challenge(
            "include K and a double letter",
            lambda word: "k" in word and bool(_double_letters(word)),
        ),
    ),
    2.5: (
        _only_vowel("i"),
        _only_vowel("o"),
        Challenge("include V and end with E", lambda word: "v" in word and word.endswith("e")),
        Challenge("three vowels in a row", lambda word: _has_run(word, 3, vowels=True)),
    ),
    3.0: (
        Challenge("use all five vowels", lambda word: set(word) >= VOWELS),
        Challenge("two different double letters", lambda word: len(_double_letters(word)) >= 2),
        Challenge("include W and Y", lambda word: "w" in word and "y" in word),
    ),
    4.0: (
        Challenge(
            "include two of J, K, Q, V, X, Z", lambda word: len(set(word) & set("jkqvxz")) >= 2
        ),
        Challenge("use one letter four times", lambda word: max(Counter(word).values()) >= 4),
    ),
}


def multiplier_weight(base: float) -> float:
    """How likely a bonus with this base multiplier is to be picked.

    The curve peaks at 2x: 1.5x bonuses are slightly rarer than that, and
    bigger multipliers get steadily rarer (4x turns up about one game in 13).
    """
    return base**4 * math.exp(-2 * base)


def pick_bonus(rng: random.Random) -> tuple[Challenge, float]:
    """Choose a game's bonus challenge and its multiplier."""
    bases = list(BONUS_CHALLENGES)
    base = rng.choices(bases, weights=[multiplier_weight(b) for b in bases])[0]
    challenge = rng.choice(BONUS_CHALLENGES[base])
    # Nudge the multiplier by about 10% either way so no two games are quite alike.
    multiplier = round(base * rng.lognormvariate(0, 0.1), 1)
    return challenge, min(max(multiplier, 1.2), 5.0)


# A turn challenge must leave at least this many unplayed words for the letter.
MIN_CHOICES = 15
# Challenges that nearly every word for the letter meets are no challenge at all.
MAX_SHARE = 0.9
# Don't repeat any of the last this many challenges.
RECENT_TURNS = 20
# Once a fair challenge is found, look at most this far for one that keeps the bonus in reach.
SEARCH_LIMIT = 30
# Free choice, for the rare letter where no challenge works.
ANY_WORD = Challenge("any word you like", lambda word: True)


class ChallengeGame(Game):
    """A game in challenge mode.

    The rules are the same as a classic game, with a longer turn clock, plus:
    every word must meet the turn's challenge, which changes every turn, and
    words that also meet the game's bonus challenge have their points multiplied.
    """

    mode = "challenge"
    default_turn_time = 20

    def __init__(
        self,
        players: Sequence[Player],
        words: WordList,
        *,
        target_score: int = DEFAULT_TARGET_SCORE,
        turn_time: int | None = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(players, words, target_score=target_score, turn_time=turn_time, rng=rng)
        self.bonus, self.multiplier = pick_bonus(self._rng)
        self._recent: deque[Challenge] = deque(maxlen=RECENT_TURNS)
        self.challenge = self._pick_challenge()

    def check_word(self, word: str) -> str | None:
        problem = super().check_word(word)
        if problem is None and not self.challenge.test(word.lower()):
            return "doesn't meet the challenge"
        return problem

    def multiplier_for(self, word: str) -> float:
        return self.multiplier if self.bonus.test(word.lower()) else 1.0

    def play(self, word: str, seconds: float) -> int:
        points = super().play(word, seconds)
        self.challenge = self._pick_challenge()
        return points

    def skip(self) -> None:
        super().skip()
        self.challenge = self._pick_challenge()

    def _pick_challenge(self) -> Challenge:
        """Choose a fair challenge for the current letter.

        It must leave plenty of words to choose from without being met by
        nearly all of them. Challenges that leave the bonus within reach (but
        don't hand it out for free) are preferred.
        """
        options = [
            word
            for word in self.words.starting_with(self.letter)
            if word not in self.used_words and len(word) >= MIN_WORD_LENGTH
        ]
        bonus_options = [word for word in options if self.bonus.test(word)]
        fallback = best = None
        best_count = 0
        for tried, challenge in enumerate(self._shuffled_challenges()):
            if fallback and tried >= SEARCH_LIMIT:
                break
            count = sum(map(challenge.test, options))
            if count > best_count:
                best, best_count = challenge, count
            if not MIN_CHOICES <= count <= MAX_SHARE * len(options):
                continue
            with_bonus = sum(map(challenge.test, bonus_options))
            if with_bonus == count:
                continue  # Every word would earn the bonus, so it would come for free.
            if with_bonus >= 3:
                fallback = challenge
                break
            fallback = fallback or challenge
        chosen = fallback or best or ANY_WORD
        self._recent.append(chosen)
        return chosen

    def _shuffled_challenges(self) -> list[Challenge]:
        """All turn challenges in a random order, weighted by tier, skipping recent ones."""
        keyed = [
            (self._rng.random() ** (len(challenges) / TIER_WEIGHTS[tier]), challenge)
            for tier, challenges in TURN_CHALLENGES.items()
            for challenge in challenges
            if challenge not in self._recent
        ]
        keyed.sort(key=lambda pair: pair[0], reverse=True)
        return [challenge for _, challenge in keyed]
