"""Challenge mode: a new challenge and round bonus every turn, and a bonus for the whole game.

Every word must meet the turn's challenge. The round bonus adds points, such
as "+2 per S", and words that meet the game's bonus have their points
multiplied. Vowels are A, E, I, O and U; Y counts as a consonant. No
challenge or bonus depends on word length or time.
"""

from __future__ import annotations

import math
import random
import re
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
    *(_includes(pair) for pair in ("qu", "ph", "gh", "tt")),
    *(_ends_with(ending) for ending in ("est", "ist", "ate", "ity", "ous", "ive")),
    _hides("a color", "red", "tan", "blue", "pink", "gold"),
    _hides("a number", "one", "two", "six", "ten"),
    *(_hides_word(hidden) for hidden in ("and", "all", "man", "end", "art", "car", "out", "ice")),
)

TURN_CHALLENGES = (*EASY, *MEDIUM, *HARD)

# Each difficulty draws turn challenges from a bell curve over the scale above,
# from 0 (easiest) to 1 (hardest). The curves are Beta distributions, given as
# (alpha, beta); their peaks sit at about 0.02, 0.06, 0.23, 0.40 and 0.50.
CHALLENGE_CURVES = {
    "beginner": (1.1, 5.0),  # Almost always easy
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


# Game bonuses: one per game, picked at random. A word that meets it has its
# points multiplied. Each is a single, hard condition, grouped by its base
# multiplier: the fewer turns that offer plenty of words for it, the more it
# pays. None is out of reach for long, so nothing like "use all five vowels".
GAME_BONUSES = {
    1.5: (
        Challenge("include a double vowel", lambda word: bool(re.search(r"([aeiou])\1", word))),
        Challenge("more vowels than consonants", lambda word: 2 * _vowel_count(word) > len(word)),
        _only_vowel("e"),
        _only_vowel("a"),
    ),
    2.0: (
        Challenge("four consonants in a row", lambda word: _has_run(word, 4, vowels=False)),
        Challenge("no A, E, or I", lambda word: not set(word) & set("aei")),
        _only_vowel("i"),
        _only_vowel("o"),
        _only_vowel("u"),
    ),
    2.5: (
        _includes("x"),
        _includes("z"),
        _includes("q"),
    ),
    3.0: (
        Challenge("three vowels in a row", lambda word: _has_run(word, 3, vowels=True)),
        _includes("j"),
        Challenge("two double letters", lambda word: _double_letters(word) >= 2),
    ),
}
MIN_MULTIPLIER = 1.5
MAX_MULTIPLIER = 3.0


def pick_game_bonus(rng: random.Random) -> tuple[Challenge, float]:
    """Choose a game's bonus, every one equally likely, and its multiplier."""
    base, bonus = rng.choice(
        [(base, bonus) for base, bonuses in GAME_BONUSES.items() for bonus in bonuses]
    )
    # Nudge the multiplier by about 10% either way so no two games are quite alike.
    multiplier = round(base * rng.lognormvariate(0, 0.1), 1)
    return bonus, min(max(multiplier, MIN_MULTIPLIER), MAX_MULTIPLIER)


@dataclass(frozen=True)
class RoundBonus:
    """Extra points for one word, such as "+2 per E"."""

    text: str
    points: Callable[[str], int]


def _per_letter(letter: str, value: int) -> RoundBonus:
    return RoundBonus(f"+{value} per {letter.upper()}", lambda word: value * word.count(letter))


def _vowel_pairs(word: str) -> int:
    return sum(a in VOWELS and b in VOWELS for a, b in pairwise(word))


def _double_letters(word: str) -> int:
    return len(re.findall(r"(.)\1", word))


# Round bonuses: a new one every word, adding points to whatever the word
# scores. They always stack, paying for each letter or pair: "+2 per S" is
# worth +8 for ASSESS. Flat conditions, like "end with a vowel", are turn
# challenges instead. Rarer letters are worth more: +2 for the commonest,
# up to +7 for Z, X, J and Q.
ROUND_BONUSES = (
    *(_per_letter(letter, 2) for letter in "eaisrntol"),
    *(_per_letter(letter, 3) for letter in "cdumgph"),
    *(_per_letter(letter, 4) for letter in "by"),
    RoundBonus("+4 per vowel pair", lambda word: 4 * _vowel_pairs(word)),
    RoundBonus("+4 per double letter", lambda word: 4 * _double_letters(word)),
    *(_per_letter(letter, 5) for letter in "fvkw"),
    *(_per_letter(letter, 7) for letter in "zxjq"),
)
NO_ROUND_BONUS = RoundBonus("no round bonus", lambda word: 0)


def _earning_share(bonus: RoundBonus, words: Sequence[str]) -> float:
    """The share of *words* that earn any points from *bonus*."""
    return sum(bonus.points(word) > 0 for word in words) / max(len(words), 1)


# A turn challenge must leave at least this many unplayed words for the letter.
MIN_CHOICES = 100
# Challenges that nearly every word for the letter meets are no challenge at all.
MAX_SHARE = 0.9
# A challenge whose words nearly all earn the game bonus would hand it out.
FREE_BONUS_SHARE = 0.8
# Don't repeat any of the last this many challenges.
RECENT_TURNS = 20
# Once a fair challenge is found, look at most this far for one that keeps the bonus in reach.
SEARCH_LIMIT = 30
# Free choice, for letters like X where no challenge leaves enough words.
ANY_WORD = Challenge("any word you like", lambda word: True)
# Once time points reach zero, they stay there this many seconds before going negative.
GRACE_SECONDS = 4


class ChallengeGame(Game):
    """A game in challenge mode.

    The rules are the same as a classic game, with a higher target, plus:

    - every word must meet the turn's challenge, which changes every turn;
    - each turn has a round bonus that adds points, such as "+2 per S";
    - words that meet the game's bonus have their points multiplied;
    - time points start at half the turn time (+10) and drop a point every 2
      seconds. At zero there are a few seconds of grace, then they drop a
      point a second.

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
        self.bonus, self.multiplier = pick_game_bonus(self._rng)
        self._recent: deque[Challenge] = deque(maxlen=RECENT_TURNS)
        self.round_bonus = NO_ROUND_BONUS
        self.challenge = self._pick_challenge()
        self.round_bonus = self._pick_round_bonus()

    def check_word(self, word: str) -> str | None:
        problem = super().check_word(word)
        if problem is None and not self.challenge.test(word.lower()):
            return "doesn't meet the challenge"
        return problem

    def multiplier_for(self, word: str) -> float:
        return self.multiplier if self.bonus.test(word.lower()) else 1.0

    def round_points(self, word: str) -> int:
        return self.round_bonus.points(word.lower())

    def time_points(self, seconds: float) -> int:
        """A point per 2 seconds left, then nothing for a few seconds, then -1 a second."""
        left = self.turn_time - seconds
        if left > 0:
            return math.ceil(left / 2)
        return min(0, math.floor(left + GRACE_SECONDS))

    def play(self, word: str, seconds: float) -> int:
        points = super().play(word, seconds)
        self.challenge = self._pick_challenge()
        self.round_bonus = self._pick_round_bonus()
        return points

    def skip(self) -> None:
        super().skip()
        self.challenge = self._pick_challenge()
        self.round_bonus = self._pick_round_bonus()

    def _unplayed_words(self) -> list[str]:
        return [
            word
            for word in self.words.starting_with(self.letter)
            if word not in self.used_words and len(word) >= MIN_WORD_LENGTH
        ]

    def _pick_challenge(self) -> Challenge:
        """Choose a fair challenge for the current letter.

        It must leave at least MIN_CHOICES words to choose from without being
        met by nearly all of them. Challenges that leave the game bonus within
        reach, without handing it out, are preferred. If no challenge leaves
        enough words, any word will do.
        """
        options = self._unplayed_words()
        bonus_options = [word for word in options if self.bonus.test(word)]
        # No challenge can stop a Z turn handing out the bonus "include Z".
        bonus_comes_anyway = len(bonus_options) > FREE_BONUS_SHARE * len(options)
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
            if with_bonus > FREE_BONUS_SHARE * count and not bonus_comes_anyway:
                continue  # Like "include QU" with the bonus "include Q"
            if with_bonus >= 3:
                fallback = challenge
                break
            fallback = fallback or challenge  # Like "no letter E" with "E is the only vowel"
        if fallback is None and best_count >= MIN_CHOICES:
            fallback = best  # Leaves enough words, though nearly all of them
        chosen = fallback or ANY_WORD
        self._recent.append(chosen)
        return chosen

    def _pick_round_bonus(self) -> RoundBonus:
        """Choose a new round bonus that this turn doesn't spoil.

        A bonus is spoiled if nearly every word that meets the challenge earns
        it, like "+2 per R" with "include R" or on an R turn, or if the
        challenge all but rules it out, like "+2 per R" with "no letter R".
        """
        options = self._unplayed_words()
        matches = [word for word in options if self.challenge.test(word)] or options
        bonuses = [bonus for bonus in ROUND_BONUSES if bonus is not self.round_bonus]
        self._rng.shuffle(bonuses)
        for bonus in bonuses:
            earned, usually = _earning_share(bonus, matches), _earning_share(bonus, options)
            if 0 < earned <= 0.95 and earned >= usually / 4:
                return bonus
        return bonuses[0]

    def _shuffled_challenges(self) -> list[Challenge]:
        """Turn challenges in a random order that favors likelier ones, skipping recent ones."""
        keyed = [
            (self._rng.random() ** (1 / weight), challenge)
            for challenge, weight in zip(TURN_CHALLENGES, self._weights, strict=True)
            if challenge not in self._recent
        ]
        keyed.sort(key=lambda pair: pair[0], reverse=True)
        return [challenge for _, challenge in keyed]
