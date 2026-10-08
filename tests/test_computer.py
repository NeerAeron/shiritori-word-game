import random

import pytest

from shiritori.challenges import ANY_WORD, Challenge, ChallengeGame
from shiritori.computer import (
    DIFFICULTIES,
    Difficulty,
    choose_word,
    thinking_time,
    typing_delays,
)
from shiritori.game import Game, Player
from shiritori.words import WordList

WORDS = WordList.default()


def make_game(letter, words=WORDS):
    game = Game([Player("Ann"), Player("Bob")], words)
    game.letter = letter
    return game


@pytest.mark.parametrize("difficulty", DIFFICULTIES.values(), ids=DIFFICULTIES)
def test_chooses_playable_words_of_the_right_length(difficulty):
    rng = random.Random(0)
    max_length = difficulty.max_length or float("inf")
    for letter in "AEKSTZ":
        game = make_game(letter)
        for _ in range(20):
            word = choose_word(game, difficulty, rng)
            assert game.check_word(word) is None
            assert difficulty.min_length <= len(word) <= max_length


def test_harder_difficulties_play_longer_words():
    rng = random.Random(0)
    game = make_game("S")
    averages = [
        sum(len(choose_word(game, difficulty, rng)) for _ in range(50)) / 50
        for difficulty in DIFFICULTIES.values()
    ]
    assert averages == sorted(averages)


def test_never_repeats_a_word():
    game = make_game("A", WordList(["apple", "axe", "avocado"]))
    game.used_words.update({"apple", "axe"})
    assert choose_word(game, DIFFICULTIES["easy"], random.Random(0)) == "avocado"


def test_falls_back_to_other_lengths_when_none_fit():
    game = make_game("A", WordList(["abracadabra"]))
    assert choose_word(game, DIFFICULTIES["easy"], random.Random(0)) == "abracadabra"


def test_returns_none_when_stumped():
    game = make_game("Q", WordList(["apple"]))
    assert choose_word(game, DIFFICULTIES["easy"], random.Random(0)) is None


def test_same_seed_same_word():
    game = make_game("M")
    difficulty = Difficulty(
        "test", 5, 9, mean_length=7, stdev=1, bonus_chance=0, challenge_thinking=3
    )
    first = choose_word(game, difficulty, random.Random(42))
    assert choose_word(game, difficulty, random.Random(42)) == first


def test_typing_delays_cover_each_letter_and_enter():
    delays = typing_delays("apple", random.Random(0), thinking=2.0)
    assert len(delays) == len("apple") + 1
    assert all(delay > 0 for delay in delays)
    assert delays[0] >= 2.0  # includes time to think of the word


def challenge_game(letter, words, bonus_test):
    game = ChallengeGame([Player("Ann"), Player("Bob")], words, rng=random.Random(0))
    game.letter = letter
    game.challenge = ANY_WORD
    game.bonus = Challenge("test bonus", bonus_test)
    game.multiplier = 2.0
    return game


def test_goes_for_the_bonus_as_often_as_its_difficulty_says():
    game = challenge_game("A", WordList(["apple", "axe", "avocado"]), lambda word: "x" in word)
    always = Difficulty("test", 3, 9, 5, 1, bonus_chance=1, challenge_thinking=3)
    never = Difficulty("test", 3, 9, 5, 1, bonus_chance=0, challenge_thinking=3)
    rng = random.Random(0)

    assert {choose_word(game, always, rng) for _ in range(20)} == {"axe"}
    assert {choose_word(game, never, rng) for _ in range(50)} == {"apple", "axe", "avocado"}


def test_plays_any_word_when_the_bonus_is_out_of_reach():
    game = challenge_game("A", WordList(["apple"]), lambda word: "z" in word)
    always = Difficulty("test", 3, 9, 5, 1, bonus_chance=1, challenge_thinking=3)
    assert choose_word(game, always, random.Random(0)) == "apple"


def test_thinks_longer_in_challenge_mode_and_longest_for_the_bonus():
    words = WordList(["apple", "axe"])
    classic = make_game("A", words)
    challenge = challenge_game("A", words, lambda word: "x" in word)
    medium = DIFFICULTIES["medium"]

    def average(game, word):
        rng = random.Random(0)
        return sum(thinking_time(game, medium, word, rng) for _ in range(200)) / 200

    assert average(classic, "apple") == pytest.approx(0.9, abs=0.1)
    assert average(challenge, "apple") == pytest.approx(medium.challenge_thinking, rel=0.1)
    assert average(challenge, "axe") == pytest.approx(medium.challenge_thinking + 2.5, rel=0.1)


def test_easier_computers_think_slower_in_challenge_mode():
    thinking = [difficulty.challenge_thinking for difficulty in DIFFICULTIES.values()]
    assert thinking == sorted(thinking, reverse=True)
    chances = [difficulty.bonus_chance for difficulty in DIFFICULTIES.values()]
    assert chances == sorted(chances)
