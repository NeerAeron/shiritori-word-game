import random
import re
from collections import Counter

import pytest

from shiritori.challenges import (
    ANY_WORD,
    BONUS_CHALLENGES,
    MIN_CHOICES,
    RECENT_TURNS,
    TURN_CHALLENGES,
    Challenge,
    ChallengeGame,
    multiplier_weight,
    pick_bonus,
)
from shiritori.game import Game, Player
from shiritori.words import WordList

WORDS = WordList.default()
ALL_TURN_CHALLENGES = [c for challenges in TURN_CHALLENGES.values() for c in challenges]
ALL_BONUSES = [c for challenges in BONUS_CHALLENGES.values() for c in challenges]


def make_game(seed=0, **options):
    return ChallengeGame([Player("Ann"), Player("Bob")], WORDS, rng=random.Random(seed), **options)


def test_there_are_100_different_turn_challenges():
    assert len(ALL_TURN_CHALLENGES) == 100
    assert len({challenge.text for challenge in ALL_TURN_CHALLENGES}) == 100


@pytest.mark.parametrize("challenge", ALL_TURN_CHALLENGES + ALL_BONUSES, ids=lambda c: c.text)
def test_no_challenge_is_about_word_length(challenge):
    banned = r"\d|letters? long|or more letters|or fewer|\b(seconds|clock|time)\b"
    assert not re.search(banned, challenge.text)


@pytest.mark.parametrize("challenge", ALL_TURN_CHALLENGES, ids=lambda c: c.text)
def test_turn_challenges_are_never_too_hard(challenge):
    share = sum(map(challenge.test, WORDS)) / len(WORDS)
    assert share >= 0.005


@pytest.mark.parametrize("bonus", ALL_BONUSES, ids=lambda c: c.text)
def test_bonus_challenges_are_hard_but_doable(bonus):
    share = sum(map(bonus.test, WORDS)) / len(WORDS)
    assert 0.005 <= share <= 0.15


@pytest.mark.parametrize(
    ("text", "yes", "no"),
    [
        ("end with S", "cats", "cat"),
        ("include a double letter", "apple", "ape"),
        ("no letter E", "cat", "tree"),
        ("exactly one vowel", "strength", "banana"),
        ("use the first letter again", "dad", "dog"),
        ("alternate consonants and vowels", "banana", "bread"),
        ("end with the letter you start with", "tent", "tend"),
        ("hide an animal (ANT, BAT, CAT, COW, DOG, HEN, OWL, PIG, RAT)", "plant", "plane"),
        ("three consonants in a row", "strong", "stone"),
        ("use one letter three times", "banana", "band"),
        ("four consonants in a row", "length", "strong"),
        ("no letter A or E", "song", "sang"),
    ],
)
def test_turn_challenges_check_what_they_say(text, yes, no):
    challenge = next(c for c in ALL_TURN_CHALLENGES if c.text == text)
    assert challenge.test(yes)
    assert not challenge.test(no)


@pytest.mark.parametrize(
    ("text", "yes", "no"),
    [
        ("use all five vowels", "education", "elephant"),
        ("two different double letters", "coffee", "apple"),
        ("include two of J, K, Q, V, X, Z", "jinx", "jam"),
        ("more vowels than consonants", "audio", "studio"),
        ("A is the only vowel", "banana", "bandit"),
        ("no A, E, or I", "song", "sing"),
        ("a double letter and end with Y", "happy", "happen"),
        ("use one letter four times", "assess", "asses"),
        ("three vowels in a row", "beautiful", "bread"),
    ],
)
def test_bonus_challenges_check_what_they_say(text, yes, no):
    bonus = next(c for c in ALL_BONUSES if c.text == text)
    assert bonus.test(yes)
    assert not bonus.test(no)


def test_bonus_multipliers_peak_at_two_with_big_ones_rare():
    weights = {base: multiplier_weight(base) for base in BONUS_CHALLENGES}
    assert max(weights, key=weights.get) == 2.0
    assert weights[1.5] < weights[2.0]  # small multipliers are slightly rarer...
    assert weights[1.5] > 0.8 * weights[2.0]
    assert weights[2.0] > weights[2.5] > weights[3.0] > weights[4.0]  # ...big ones much rarer
    assert weights[4.0] < 0.35 * weights[2.0]


def test_picked_multipliers_follow_the_curve_with_a_little_randomness():
    rng = random.Random(1)
    picks = [pick_bonus(rng) for _ in range(5000)]
    base_of = {c.text: base for base, challenges in BONUS_CHALLENGES.items() for c in challenges}

    tiers = Counter(base_of[challenge.text] for challenge, _ in picks)
    assert tiers.most_common(1)[0][0] == 2.0
    assert tiers[4.0] < tiers[1.5] < tiers[2.0]

    nudges = [multiplier / base_of[challenge.text] for challenge, multiplier in picks]
    assert sum(abs(nudge - 1) <= 0.2 for nudge in nudges) / len(nudges) > 0.95
    assert all(1.2 <= multiplier <= 5.0 for _, multiplier in picks)
    assert all(multiplier == round(multiplier, 1) for _, multiplier in picks)
    assert len({multiplier for _, multiplier in picks}) > 10  # not just the base values


def test_words_must_meet_the_turn_challenge():
    game = make_game()
    game.letter = "C"
    game.challenge = next(c for c in ALL_TURN_CHALLENGES if c.text == "end with S")
    assert game.check_word("cat") == "doesn't meet the challenge"
    assert game.check_word("cats") is None
    assert game.check_word("dogs") == "must start with C"  # the usual rules come first


def test_meeting_the_bonus_multiplies_the_points():
    game = make_game()
    game.letter = "C"
    game.challenge = ANY_WORD
    game.bonus, game.multiplier = Challenge("include Z", lambda word: "z" in word), 2.5

    assert game.score("cat", seconds=0) == 23  # 3 letters + 20 seconds left
    assert game.score("craze", seconds=5) == round((5 + 15) * 2.5)
    assert game.score("craze", seconds=30) == 5 - 10  # no bonus on a penalty
    game.play("craze", seconds=5)
    assert game.moves[-1].multiplier == 2.5
    assert game.players[0].score == 50


def test_has_a_longer_clock_than_classic():
    assert make_game().turn_time == 20 > Game.default_turn_time
    assert make_game(turn_time=8).turn_time == 8


def test_every_turn_gets_a_new_fair_challenge():
    game = make_game(seed=3)
    seen = []
    for _ in range(40):
        options = [w for w in WORDS.starting_with(game.letter) if game.check_word(w) is None]
        assert len(options) >= MIN_CHOICES
        seen.append(game.challenge)
        game.play(random.Random(len(seen)).choice(options), seconds=1)

    for i, challenge in enumerate(seen):
        assert challenge not in seen[max(0, i - RECENT_TURNS) : i]


def test_prefers_challenges_that_keep_the_bonus_in_reach():
    reachable = 0
    for seed in range(30):
        game = make_game(seed=seed)
        words = [w for w in WORDS.starting_with(game.letter) if game.check_word(w) is None]
        bonus_words = [w for w in words if game.multiplier_for(w) > 1]
        assert len(bonus_words) < len(words)  # the bonus never comes for free
        reachable += len(bonus_words) >= 3
    assert reachable >= 25


def test_skipping_picks_a_new_letter_and_challenge():
    game = make_game(seed=5)
    game.skip()
    assert game.current_player is game.players[1]
    assert game.challenge in ALL_TURN_CHALLENGES or game.challenge is ANY_WORD


def test_falls_back_when_few_words_are_left():
    words = WordList(["xenon", "xerox", "xylem"])
    game = ChallengeGame([Player("Ann"), Player("Bob")], words, rng=random.Random(0))
    game.letter = "X"
    challenge = game._pick_challenge()
    assert any(challenge.test(word) for word in ("xenon", "xerox", "xylem"))
