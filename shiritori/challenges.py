"""Challenge mode: a new spelling challenge every turn, and a bonus challenge for the whole game.

Every word must meet the turn's challenge. Words that also meet the game's
bonus challenge have their points multiplied. Vowels are A, E, I, O and U;
Y counts as a consonant. No challenge depends on word length or time.
"""

from __future__ import annotations

import random
from collections import Counter, deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from .game import MIN_WORD_LENGTH, Game, Player
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


def _hides_word(hidden: str) -> Challenge:
    return Challenge(f"hide the word {hidden.upper()}", lambda word: hidden in word)


def _only_vowel(vowel: str) -> Challenge:
    return Challenge(
        f"{vowel.upper()} is the only vowel", lambda word: set(word) & VOWELS == {vowel}
    )


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


def _has_double(word: str) -> bool:
    return any(a == b for a, b in pairwise(word))


def _is_consonant(letter: str) -> bool:
    return letter not in VOWELS


# Turn challenges, from easiest to hardest. Each list is in order of difficulty
# too, so together they rank every challenge on one scale.
EASY = (
    *(_without(letter) for letter in "otn"),
    _includes("r"),
    Challenge("second letter is a vowel", lambda word: word[1] in VOWELS),
    *(_without(letter) for letter in "rsai"),
    _includes("l"),
    Challenge(
        "end with two consonants", lambda word: _is_consonant(word[-1]) and _is_consonant(word[-2])
    ),
    _includes("d"),
    *(_ends_with(letter) for letter in "se"),
    *(_includes(letter) for letter in "cumpgbhy"),
    Challenge("end with a vowel", lambda word: word[-1] in VOWELS),
    *(_ends_with(letter) for letter in "ydtnr"),
    Challenge("third letter is a vowel", lambda word: word[2] in VOWELS),
    Challenge("second letter is a consonant", lambda word: _is_consonant(word[1])),
    Challenge("two vowels in a row", lambda word: _has_run(word, 2, vowels=True)),
    Challenge("include a double letter", _has_double),
    *(_includes(pair) for pair in ("er", "in")),
    *(_ends_with(ending) for ending in ("er", "ed", "es", "ing")),
    Challenge("exactly one vowel", lambda word: _vowel_count(word) == 1),
    Challenge("exactly two vowels", lambda word: _vowel_count(word) == 2),
    Challenge("use only one kind of vowel", lambda word: len(set(word) & VOWELS) == 1),
    Challenge("no letter used twice", lambda word: len(set(word)) == len(word)),
)

MEDIUM = (
    _without("e"),
    _without("i", "o"),
    _without("a", "o"),
    _without("a", "i"),
    *(_includes(letter) for letter in "fkwv"),
    *(_ends_with(letter) for letter in "lagkhop"),
    *(_ends_with(ending) for ending in ("st", "nt", "nd", "ck", "le", "ly", "al", "ic", "ion")),
    Challenge("end with three consonants", lambda word: all(map(_is_consonant, word[-3:]))),
    Challenge("end with two vowels", lambda word: word[-1] in VOWELS and word[-2] in VOWELS),
    Challenge("end with a double letter", lambda word: word[-1] == word[-2]),
    Challenge("end with the letter you start with", lambda word: word[-1] == word[0]),
    *(_includes(pair) for pair in ("th", "sh", "ch", "ck", "st", "ll", "ss")),
    *(_includes(pair) for pair in ("ee", "oo", "ea", "ou", "ie", "ow", "ai", "oa")),
    *(_second_letter(letter) for letter in "rlh"),
    Challenge("use the first letter again", lambda word: word[0] in word[1:]),
    Challenge("three consonants in a row", lambda word: _has_run(word, 3, vowels=False)),
    Challenge(
        "alternate consonants and vowels",
        lambda word: all((a in VOWELS) != (b in VOWELS) for a, b in pairwise(word)),
    ),
    Challenge(
        "end with a vowel and include a double letter",
        lambda word: word[-1] in VOWELS and _has_double(word),
    ),
    _hides("an animal", "ant", "bat", "cat", "cow", "dog", "hen", "owl", "pig", "rat"),
    _hides("a body part", "arm", "ear", "eye", "hip", "leg", "lip", "rib", "toe"),
    _hides_word("ate"),
    _hides_word("her"),
)

HARD = (
    Challenge("use one letter three times", lambda word: max(Counter(word).values()) >= 3),
    _without("a", "e"),
    _without("e", "i"),
    *(_includes(letter) for letter in "zxj"),
    *(_includes(pair) for pair in ("qu", "ph", "gh", "tt")),
    Challenge("four consonants in a row", lambda word: _has_run(word, 4, vowels=False)),
    Challenge("start with three consonants", lambda word: all(map(_is_consonant, word[:3]))),
    *(_ends_with(ending) for ending in ("est", "ist", "ate", "ity", "ous", "ive", "age", "ish")),
    *(_ends_with(ending) for ending in ("ness", "less", "ment")),
    _hides("a color", "red", "tan", "blue", "pink", "gold"),
    _hides("a number", "one", "two", "six", "ten"),
    *(_hides_word(hidden) for hidden in ("and", "all", "man", "end", "art", "car", "out")),
    *(_hides_word(hidden) for hidden in ("pin", "use", "ice")),
)

TURN_CHALLENGES = (*EASY, *MEDIUM, *HARD)

# Each difficulty draws turn challenges from a bell curve over the scale above,
# from 0 (easiest) to 1 (hardest). The curves are Beta distributions, given as
# (alpha, beta); their peaks sit at about 0.06, 0.23, 0.40 and 0.50.
CHALLENGE_CURVES = {
    "easy": (1.2, 4.0),  # Heavily toward the easy end
    "medium": (1.6, 3.0),  # Toward the easy end
    "hard": (2.0, 2.5),  # Slightly toward the easy end
    "impossible": (2.0, 2.0),  # Centered
}
# Games between people use the same mix of challenges as a hard computer.
DEFAULT_DIFFICULTY = "hard"


def challenge_weights(difficulty: str) -> list[float]:
    """How likely each turn challenge is to come up at *difficulty*, in TURN_CHALLENGES order."""
    alpha, beta = CHALLENGE_CURVES[difficulty]
    count = len(TURN_CHALLENGES)
    positions = ((rank + 0.5) / count for rank in range(count))
    return [x ** (alpha - 1) * (1 - x) ** (beta - 1) for x in positions]


def _double_and(word: str, test: Callable[[str], bool]) -> bool:
    return _has_double(word) and test(word)


# Bonus challenges by their multiplier before the random nudge: harder ones pay
# more. Every game picks one of them at random, each equally likely, so how many
# sit at each multiplier sets how common it is: 2x is the most common, 1.5x is
# slightly rarer, and 3x, the most a bonus can pay, is rarer still.
BONUS_CHALLENGES = {
    1.5: (
        Challenge("include J, Q, X, or Z", lambda word: bool(set(word) & set("jqxz"))),
        Challenge(
            "use the same vowel three times",
            lambda word: any(word.count(vowel) >= 3 for vowel in VOWELS),
        ),
        Challenge("no A, E, or I", lambda word: not set(word) & set("aei")),
        Challenge("no E, I, or O", lambda word: not set(word) & set("eio")),
        Challenge("no A, E, or O", lambda word: not set(word) & set("aeo")),
        Challenge("include four different vowels", lambda word: len(set(word) & VOWELS) >= 4),
        Challenge(
            "a double letter and no E", lambda word: _double_and(word, lambda w: "e" not in w)
        ),
    ),
    2.0: (
        Challenge("more vowels than consonants", lambda word: 2 * _vowel_count(word) > len(word)),
        _only_vowel("a"),
        _only_vowel("e"),
        _only_vowel("u"),
        Challenge(
            "a double letter and end with Y",
            lambda word: _double_and(word, lambda w: w.endswith("y")),
        ),
        Challenge(
            "a double letter and end with E",
            lambda word: _double_and(word, lambda w: w.endswith("e")),
        ),
        Challenge("no E and end with Y", lambda word: "e" not in word and word.endswith("y")),
        Challenge("include P and end with Y", lambda word: "p" in word and word.endswith("y")),
        Challenge("include H and end with Y", lambda word: "h" in word and word.endswith("y")),
        Challenge(
            "include B and a double letter", lambda word: _double_and(word, lambda w: "b" in w)
        ),
    ),
    2.5: (
        _only_vowel("i"),
        _only_vowel("o"),
        Challenge("three vowels in a row", lambda word: _has_run(word, 3, vowels=True)),
        Challenge("include V and end with E", lambda word: "v" in word and word.endswith("e")),
        Challenge(
            "include K and a double letter", lambda word: _double_and(word, lambda w: "k" in w)
        ),
        Challenge(
            "include F and a double letter", lambda word: _double_and(word, lambda w: "f" in w)
        ),
        Challenge(
            "include J, Q, X, or Z and end with a vowel",
            lambda word: bool(set(word) & set("jqxz")) and word[-1] in VOWELS,
        ),
        Challenge(
            "two vowels in a row and end with Y",
            lambda word: _has_run(word, 2, vowels=True) and word.endswith("y"),
        ),
    ),
    3.0: (
        Challenge("use all five vowels", lambda word: set(word) >= VOWELS),
        Challenge(
            "two different double letters",
            lambda word: len({a for a, b in pairwise(word) if a == b}) >= 2,
        ),
        Challenge("include W and Y", lambda word: "w" in word and "y" in word),
        Challenge(
            "include two of J, K, Q, V, X, Z", lambda word: len(set(word) & set("jkqvxz")) >= 2
        ),
        Challenge("use one letter four times", lambda word: max(Counter(word).values()) >= 4),
    ),
}
MAX_MULTIPLIER = 3.0


def pick_bonus(rng: random.Random) -> tuple[Challenge, float]:
    """Choose a game's bonus challenge, every one equally likely, and its multiplier."""
    base, challenge = rng.choice(
        [
            (base, challenge)
            for base, challenges in BONUS_CHALLENGES.items()
            for challenge in challenges
        ]
    )
    # Nudge the multiplier by about 10% either way so no two games are quite alike.
    multiplier = round(base * rng.lognormvariate(0, 0.1), 1)
    return challenge, min(max(multiplier, 1.2), MAX_MULTIPLIER)


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
    *difficulty* sets how hard the turn challenges tend to be.
    """

    mode = "challenge"
    default_target_score = 150
    default_turn_time = 20

    def __init__(
        self,
        players: Sequence[Player],
        words: WordList,
        *,
        target_score: int | None = None,
        turn_time: int | None = None,
        difficulty: str = DEFAULT_DIFFICULTY,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(players, words, target_score=target_score, turn_time=turn_time, rng=rng)
        self.difficulty = difficulty
        self._weights = challenge_weights(difficulty)
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
        """Turn challenges in a random order that favors likelier ones, skipping recent ones."""
        keyed = [
            (self._rng.random() ** (1 / weight), challenge)
            for challenge, weight in zip(TURN_CHALLENGES, self._weights, strict=True)
            if challenge not in self._recent
        ]
        keyed.sort(key=lambda pair: pair[0], reverse=True)
        return [challenge for _, challenge in keyed]
