import random
import re
from collections import Counter
from itertools import pairwise

import pytest

from shiritori.challenges import (
    ANY_WORD,
    CHALLENGE_CURVES,
    EASY,
    GAME_BONUSES,
    HARD,
    MAX_MULTIPLIER,
    MAX_SHARE,
    MEDIUM,
    MIN_CHOICES,
    MIN_MULTIPLIER,
    RECENT_TURNS,
    ROUND_BONUSES,
    TURN_CHALLENGES,
    Challenge,
    ChallengeGame,
    RoundBonus,
    challenge_weights,
    pick_game_bonus,
)
from shiritori.game import STARTING_LETTERS, Game, Player
from shiritori.words import WordList

WORDS = WordList.default()
ALL_BONUSES = [bonus for bonuses in GAME_BONUSES.values() for bonus in bonuses]
TIER_OF = {
    c.text: tier for tier, cs in (("easy", EASY), ("medium", MEDIUM), ("hard", HARD)) for c in cs
}


def make_game(seed=0, **options):
    return ChallengeGame([Player("Ann"), Player("Bob")], WORDS, rng=random.Random(seed), **options)


def test_there_are_over_110_different_turn_challenges():
    assert len(TURN_CHALLENGES) >= 110
    assert len({challenge.text for challenge in TURN_CHALLENGES}) == len(TURN_CHALLENGES)
    assert (*EASY, *MEDIUM, *HARD) == TURN_CHALLENGES


def test_there_are_15_different_game_bonuses():
    assert len(ALL_BONUSES) == 15
    assert len({bonus.text for bonus in ALL_BONUSES}) == 15
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
def test_game_bonuses_are_hard(bonus):
    share = sum(map(bonus.test, WORDS)) / len(WORDS)
    assert 0.01 <= share <= 0.06


@pytest.mark.parametrize("bonus", ALL_BONUSES, ids=lambda c: c.text)
def test_game_bonuses_are_never_out_of_reach_for_long(bonus):
    # Unlike, say, "use all five vowels": no starting letter has 10 short words for it.
    def plenty(letter):
        return sum(len(word) <= 8 and bonus.test(word) for word in WORDS.starting_with(letter))

    assert sum(plenty(letter) >= 10 for letter in STARTING_LETTERS) >= len(STARTING_LETTERS) / 2


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
        ("use one letter three times", "banana", "band"),
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
        ("include a double vowel", "moon", "moan"),
        ("more vowels than consonants", "audio", "studio"),
        ("E is the only vowel", "tree", "tire"),
        ("A is the only vowel", "banana", "bandit"),
        ("four consonants in a row", "length", "strong"),
        ("no A, E, or I", "song", "sing"),
        ("I is the only vowel", "fishing", "fished"),
        ("O is the only vowel", "cotton", "button"),
        ("U is the only vowel", "dusty", "dusted"),
        ("include X", "taxi", "talk"),
        ("include Z", "pizza", "pita"),
        ("include Q", "quiet", "diet"),
        ("three vowels in a row", "beautiful", "bread"),
        ("include J", "enjoy", "envoy"),
        ("two double letters", "coffee", "apple"),
    ],
)
def test_game_bonuses_check_what_they_say(text, yes, no):
    bonus = next(c for c in ALL_BONUSES if c.text == text)
    assert bonus.test(yes)
    assert not bonus.test(no)


def test_game_bonus_multipliers_peak_at_two_and_stay_between_one_and_a_half_and_three():
    counts = {base: len(bonuses) for base, bonuses in GAME_BONUSES.items()}
    assert max(counts, key=counts.get) == 2.0
    assert counts[1.5] < counts[2.0]  # small multipliers are slightly rarer...
    assert counts[3.0] == min(counts.values())  # ...and the biggest are rarest
    assert MIN_MULTIPLIER == 1.5 == min(GAME_BONUSES)
    assert MAX_MULTIPLIER == 3.0 == max(GAME_BONUSES)


def test_every_game_bonus_is_equally_likely_with_a_little_randomness():
    rng = random.Random(1)
    picks = [pick_game_bonus(rng) for _ in range(30_000)]
    base_of = {bonus.text: base for base, bonuses in GAME_BONUSES.items() for bonus in bonuses}

    counts = Counter(bonus.text for bonus, _ in picks)
    assert len(counts) == 15
    assert all(1800 <= count <= 2200 for count in counts.values())  # about 2,000 each

    nudges = [multiplier / base_of[bonus.text] for bonus, multiplier in picks]
    assert sum(abs(nudge - 1) <= 0.2 for nudge in nudges) / len(nudges) > 0.95
    assert all(1.5 <= multiplier <= 3.0 for _, multiplier in picks)
    assert all(multiplier == round(multiplier, 1) for _, multiplier in picks)
    assert len({multiplier for _, multiplier in picks}) > 10  # not just the base values


def test_there_is_a_short_round_bonus_for_every_letter_and_two_pairs():
    texts = [bonus.text for bonus in ROUND_BONUSES]
    assert len(texts) == 28
    assert len(set(texts)) == len(texts)
    assert all(re.fullmatch(r"\+\d+ per [A-Z]|\+\d+ per [a-z ]+", text) for text in texts)
    assert max(map(len, texts)) <= 20


@pytest.mark.parametrize("bonus", ROUND_BONUSES, ids=lambda b: b.text)
def test_round_bonuses_always_stack(bonus):
    earning = [w for w in ("queue", "assess", "bookkeeper", "pizzazz", "jinx") if bonus.points(w)]
    earning += [w for w in WORDS.starting_with("b") if bonus.points(w)][:50]
    assert earning
    for word in earning:  # The word twice over earns at least twice as much
        assert bonus.points(word * 2) >= 2 * bonus.points(word)


@pytest.mark.parametrize(
    ("text", "word", "points"),
    [
        ("+2 per S", "assess", 8),
        ("+2 per E", "excellence", 8),
        ("+3 per D", "added", 9),
        ("+4 per Y", "yearly", 8),
        ("+5 per K", "kayak", 10),
        ("+10 per Z", "pizzazz", 40),
        ("+10 per Q", "cat", 0),
        ("+3 per vowel pair", "queue", 9),
        ("+3 per double letter", "bookkeeper", 9),
    ],
)
def test_round_bonuses_add_what_they_say(text, word, points):
    bonus = next(b for b in ROUND_BONUSES if b.text == text)
    assert bonus.points(word) == points


def test_rarer_letters_earn_more_round_bonus_points():
    value = {}
    for bonus in ROUND_BONUSES:
        if match := re.fullmatch(r"\+(\d+) per ([A-Z])", bonus.text):
            value[match[2].lower()] = int(match[1])
    assert sorted(value) == list("abcdefghijklmnopqrstuvwxyz")

    def share(letter):
        return sum(letter in word for word in WORDS) / len(WORDS)

    by_share = sorted(value, key=share, reverse=True)
    assert [value[letter] for letter in by_share] == sorted(value.values())
    assert value["s"] == value["e"] == min(value.values()) == 2
    assert value["z"] == value["q"] == 10


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
    assert impossible["easy"] < easy["easy"]
    assert impossible["medium"] > easy["medium"]
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


@pytest.mark.parametrize(
    ("seconds", "points"),
    [(0, 10), (1.9, 10), (2, 9), (5, 8), (18.5, 1), (20, 0), (23.9, 0), (24.5, -1), (30.5, -7)],
)
def test_time_points_drop_one_every_2_seconds_then_wait_4_seconds_before_going_negative(
    seconds, points
):
    assert make_game().time_points(seconds) == points


def test_time_points_start_at_half_the_turn_time():
    assert make_game(turn_time=30).time_points(0) == 15


def test_meeting_the_bonus_multiplies_the_points():
    game = make_game()
    game.letter = "C"
    game.challenge = ANY_WORD
    game.round_bonus = RoundBonus("+10 per X", lambda word: 10 * word.count("x"))
    game.bonus, game.multiplier = Challenge("include Z", lambda word: "z" in word), 2.5

    assert game.score("cat", seconds=0) == 13  # 3 letters + 10 time points
    assert game.score("craze", seconds=6) == (5 + 7) * 2.5
    assert game.score("craze", seconds=30) == 5 - 6  # no bonus on a penalty
    game.play("craze", seconds=6)
    assert game.moves[-1].multiplier == 2.5
    assert game.players[0].score == 30


def test_the_round_bonus_adds_points_before_the_multiplier():
    game = make_game()
    game.letter = "C"
    game.challenge = ANY_WORD
    game.round_bonus = RoundBonus("+3 per C", lambda word: 3 * word.count("c"))
    game.bonus, game.multiplier = Challenge("include Z", lambda word: "z" in word), 2.0

    assert game.score("cat", seconds=0) == 3 + 3 + 10
    assert game.score("cozy", seconds=10) == (4 + 3 + 5) * 2
    assert game.score("circus", seconds=30) == 6 + 6 - 6  # still counts when time ran out
    game.play("circus", seconds=4)
    assert game.moves[-1].round_bonus == 6
    assert game.moves[-1].time_bonus == 8
    assert game.players[0].score == 6 + 6 + 8


def test_every_turn_gets_a_new_round_bonus():
    game = make_game(seed=4)
    bonuses = []
    for _ in range(60):
        bonuses.append(game.round_bonus)
        game.skip()
    assert all(bonus in ROUND_BONUSES for bonus in bonuses)
    assert all(a is not b for a, b in pairwise(bonuses))
    assert len(set(bonuses)) > 20


@pytest.mark.parametrize("challenge", ["include R", "no letter R", "end with R"])
def test_the_turn_never_spoils_the_round_bonus(challenge):
    game = make_game(seed=6)
    game.letter = "S"
    game.challenge = next(c for c in TURN_CHALLENGES if c.text == challenge)
    picked = set()
    for _ in range(300):
        game.round_bonus = game._pick_round_bonus()
        picked.add(game.round_bonus.text)
    assert "+2 per R" not in picked  # it would be ruled out, or come with every word
    assert "+2 per S" not in picked  # every S word earns it
    assert len(picked) > 20


def test_has_a_longer_clock_than_classic():
    assert make_game().turn_time == 20 > Game.default_turn_time
    assert make_game(turn_time=8).turn_time == 8


def test_every_turn_gets_a_new_fair_challenge():
    game = make_game(seed=3)
    seen = []
    for _ in range(40):
        options = [w for w in WORDS.starting_with(game.letter) if game.check_word(w) is None]
        assert len(options) >= MIN_CHOICES == 100
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


def test_any_word_will_do_when_no_challenge_leaves_enough_words():
    game = make_game()
    game.letter = "X"  # Only about 100 words start with X.
    assert game._pick_challenge() is ANY_WORD
    words = WordList(["xenon", "xerox", "xylem"])
    game = ChallengeGame([Player("Ann"), Player("Bob")], words, rng=random.Random(0))
    game.letter = "X"
    assert game._pick_challenge() is ANY_WORD
    assert game._pick_round_bonus() in ROUND_BONUSES


def test_avoids_challenges_that_hand_out_the_game_bonus():
    game = make_game(seed=8)
    game.letter = "S"
    game.bonus = next(bonus for bonus in ALL_BONUSES if bonus.text == "include a double vowel")
    picked = {game._pick_challenge().text for _ in range(300)}
    assert len(picked) > 50
    assert not picked & {"include EE", "include OO"}


def test_turns_that_hand_out_the_game_bonus_anyway_still_get_fair_challenges():
    game = make_game(seed=9)
    game.letter = "Z"  # Every word for the turn earns the bonus
    game.bonus = next(bonus for bonus in ALL_BONUSES if bonus.text == "include Z")
    options = game._unplayed_words()
    for _ in range(8):
        challenge = game._pick_challenge()
        assert MIN_CHOICES <= sum(map(challenge.test, options)) <= MAX_SHARE * len(options)


def test_challenge_games_play_to_200():
    assert make_game().target_score == 200
    assert Game([Player("Ann"), Player("Bob")], WORDS).target_score == 100
    assert make_game(target_score=80).target_score == 80
