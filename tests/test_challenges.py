import random
import re
from collections import Counter

import pytest

from shiritori.challenges import (
    ANY_WORD,
    BONUS_CHALLENGES,
    CHALLENGE_CURVES,
    EASY,
    HARD,
    MAX_MULTIPLIER,
    MEDIUM,
    MIN_CHOICES,
    RECENT_TURNS,
    TURN_CHALLENGES,
    Challenge,
    ChallengeGame,
    challenge_weights,
    pick_bonus,
)
from shiritori.game import Game, Player
from shiritori.words import WordList

WORDS = WordList.default()
ALL_BONUSES = [c for challenges in BONUS_CHALLENGES.values() for c in challenges]
TIER_OF = {
    c.text: tier for tier, cs in (("easy", EASY), ("medium", MEDIUM), ("hard", HARD)) for c in cs
}


def make_game(seed=0, **options):
    return ChallengeGame([Player("Ann"), Player("Bob")], WORDS, rng=random.Random(seed), **options)


def test_there_are_over_110_different_turn_challenges():
    assert len(TURN_CHALLENGES) >= 110
    assert len({challenge.text for challenge in TURN_CHALLENGES}) == len(TURN_CHALLENGES)
    assert (*EASY, *MEDIUM, *HARD) == TURN_CHALLENGES


def test_there_are_30_different_bonus_challenges():
    assert len(ALL_BONUSES) == 30
    assert len({bonus.text for bonus in ALL_BONUSES}) == 30
    assert not {bonus.text for bonus in ALL_BONUSES} & {c.text for c in TURN_CHALLENGES}


@pytest.mark.parametrize("challenge", TURN_CHALLENGES + tuple(ALL_BONUSES), ids=lambda c: c.text)
def test_no_challenge_is_about_word_length(challenge):
    banned = r"\d|letters? long|or more letters|or fewer|\b(seconds|clock|time)\b"
    assert not re.search(banned, challenge.text)


@pytest.mark.parametrize("challenge", TURN_CHALLENGES, ids=lambda c: c.text)
def test_turn_challenges_are_never_too_hard(challenge):
    share = sum(map(challenge.test, WORDS)) / len(WORDS)
    assert share >= 0.003


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
        ("end with two consonants", "hand", "hello"),
        ("end with a vowel and include a double letter", "coffee", "coffees"),
        ("start with three consonants", "string", "stone"),
        ("use one letter three times", "banana", "band"),
        ("four consonants in a row", "length", "strong"),
        ("no letter A or E", "song", "sang"),
        ("hide the word ICE", "office", "offer"),
    ],
)
def test_turn_challenges_check_what_they_say(text, yes, no):
    challenge = next(c for c in TURN_CHALLENGES if c.text == text)
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
        ("a double letter and no E", "happy", "apple"),
        ("include four different vowels", "question", "banana"),
        ("include J, Q, X, or Z and end with a vowel", "quite", "quit"),
        ("two vowels in a row and end with Y", "beauty", "baby"),
        ("use one letter four times", "assess", "asses"),
        ("three vowels in a row", "beautiful", "bread"),
    ],
)
def test_bonus_challenges_check_what_they_say(text, yes, no):
    bonus = next(c for c in ALL_BONUSES if c.text == text)
    assert bonus.test(yes)
    assert not bonus.test(no)


def test_bonus_multipliers_peak_at_two_and_never_pass_three():
    counts = {base: len(challenges) for base, challenges in BONUS_CHALLENGES.items()}
    assert max(counts, key=counts.get) == 2.0
    assert counts[1.5] < counts[2.0]  # small multipliers are slightly rarer...
    assert counts[3.0] == min(counts.values())  # ...and the biggest are rarest
    assert max(BONUS_CHALLENGES) <= MAX_MULTIPLIER == 3.0


def test_every_bonus_challenge_is_equally_likely_with_a_little_randomness():
    rng = random.Random(1)
    picks = [pick_bonus(rng) for _ in range(30_000)]
    base_of = {c.text: base for base, challenges in BONUS_CHALLENGES.items() for c in challenges}

    counts = Counter(challenge.text for challenge, _ in picks)
    assert len(counts) == 30
    assert all(800 <= count <= 1200 for count in counts.values())  # about 1,000 each

    nudges = [multiplier / base_of[challenge.text] for challenge, multiplier in picks]
    assert sum(abs(nudge - 1) <= 0.2 for nudge in nudges) / len(nudges) > 0.95
    assert all(1.2 <= multiplier <= 3.0 for _, multiplier in picks)
    assert all(multiplier == round(multiplier, 1) for _, multiplier in picks)
    assert len({multiplier for _, multiplier in picks}) > 10  # not just the base values


def tier_shares(weights):
    totals = Counter()
    for challenge, weight in zip(TURN_CHALLENGES, weights, strict=True):
        totals[TIER_OF[challenge.text]] += weight
    return {tier: totals[tier] / sum(weights) for tier in ("easy", "medium", "hard")}


def peak(weights):
    return (weights.index(max(weights)) + 0.5) / len(weights)


def test_challenge_curves_lean_easy_then_center_as_difficulty_rises():
    peaks = {name: peak(challenge_weights(name)) for name in CHALLENGE_CURVES}
    assert peaks["easy"] < 0.1  # heavily toward easy
    assert 0.15 < peaks["medium"] < 0.3  # toward easy
    assert 0.35 < peaks["hard"] < 0.45  # slightly toward easy
    assert peaks["impossible"] == pytest.approx(0.5, abs=0.01)  # centered

    impossible = challenge_weights("impossible")
    assert impossible == pytest.approx(impossible[::-1])  # a symmetric bell curve


def test_harder_games_get_harder_challenges():
    shares = {name: tier_shares(challenge_weights(name)) for name in CHALLENGE_CURVES}
    assert shares["easy"]["easy"] > 0.65
    assert shares["easy"]["hard"] < 0.05
    hard_shares = [shares[name]["hard"] for name in ("easy", "medium", "hard", "impossible")]
    assert hard_shares == sorted(hard_shares)
    assert all(share > 0 for tiers in shares.values() for share in tiers.values())


def test_games_pick_challenges_along_their_curve():
    def picked_tiers(difficulty):
        game = make_game(seed=2, difficulty=difficulty)
        tiers = Counter()
        for _ in range(150):
            tiers[TIER_OF.get(game.challenge.text, "any")] += 1
            game.skip()
        return tiers

    easy, impossible = picked_tiers("easy"), picked_tiers("impossible")
    assert easy["easy"] > easy["medium"] > easy["hard"]
    assert impossible["medium"] > impossible["easy"]
    assert impossible["hard"] > easy["hard"]


def test_games_between_people_use_hard_challenges():
    assert make_game().difficulty == "hard"


def test_words_must_meet_the_turn_challenge():
    game = make_game()
    game.letter = "C"
    game.challenge = next(c for c in TURN_CHALLENGES if c.text == "end with S")
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
    assert game.challenge in TURN_CHALLENGES or game.challenge is ANY_WORD


def test_falls_back_when_few_words_are_left():
    words = WordList(["xenon", "xerox", "xylem"])
    game = ChallengeGame([Player("Ann"), Player("Bob")], words, rng=random.Random(0))
    game.letter = "X"
    challenge = game._pick_challenge()
    assert any(challenge.test(word) for word in ("xenon", "xerox", "xylem"))


def test_challenge_games_play_to_150():
    assert make_game().target_score == 150
    assert Game([Player("Ann"), Player("Bob")], WORDS).target_score == 100
    assert make_game(target_score=80).target_score == 80
