import random

import pytest

from shiritori.computer import DIFFICULTIES, Difficulty, choose_word, typing_delays
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
    difficulty = Difficulty("test", min_length=5, max_length=9, mean_length=7, stdev=1)
    first = choose_word(game, difficulty, random.Random(42))
    assert choose_word(game, difficulty, random.Random(42)) == first


def test_typing_delays_cover_each_letter_and_enter():
    delays = typing_delays("apple", random.Random(0))
    assert len(delays) == len("apple") + 1
    assert all(delay > 0 for delay in delays)
    assert delays[0] >= 0.2  # includes time to think of the word
