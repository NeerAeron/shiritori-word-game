import math
import random
from dataclasses import replace

import pytest

from shiritori.challenges import ANY_WORD, NO_ROUND_BONUS, Challenge, ChallengeGame, RoundBonus
from shiritori.computer import (
    DIFFICULTIES,
    EASE_LENGTH,
    EASE_THINKING,
    choose_word,
    letter_ease,
    most_round_points,
    thinking_time,
    typing_delays,
)
from shiritori.game import Game, Player
from shiritori.words import WordList

WORDS = WordList.default()


def custom_difficulty(**changes):
    settings = {
        "name": "test",
        "min_length": 3,
        "max_length": 9,
        "mean_length": 5,
        "stdev": 1,
        "challenge_length_shift": 0,
    }
    return replace(DIFFICULTIES["medium"], **(settings | changes))


def make_game(letter, words=WORDS):
    game = Game([Player("Ann"), Player("Bob")], words)
    game.letter = letter
    return game


@pytest.mark.parametrize("difficulty", DIFFICULTIES.values(), ids=DIFFICULTIES)
def test_chooses_playable_words_of_the_right_length(difficulty):
    rng = random.Random(0)
    for letter in "AEKSTZ":
        game = make_game(letter)
        shift = EASE_LENGTH * letter_ease(WORDS, letter)
        for _ in range(20):
            word = choose_word(game, difficulty, rng)
            assert game.check_word(word) is None
            assert difficulty.min_length + shift <= len(word) <= difficulty.max_length + shift


def test_letter_ease_ranks_common_letters_above_awkward_ones():
    assert letter_ease(WORDS, "S") > 1
    assert letter_ease(WORDS, "y") < -2
    assert letter_ease(WORDS, "S") > letter_ease(WORDS, "E") > letter_ease(WORDS, "Y")
    assert letter_ease(WORDS, "X") == -2.5  # capped


def test_common_letters_get_longer_words_and_quicker_thinking():
    difficulty = DIFFICULTIES["medium"]

    def average(letter, measure):
        rng = random.Random(1)
        game = make_game(letter)
        return sum(measure(game, rng) for _ in range(150)) / 150

    def length(game, rng):
        return len(choose_word(game, difficulty, rng))

    def thinking(game, rng):
        return thinking_time(game, difficulty, "word", rng)

    assert average("S", length) > average("Y", length) + 1
    assert average("S", thinking) < average("Y", thinking) * 0.7


def test_harder_computers_leave_awkward_letters():
    def awkward_share(difficulty):
        rng = random.Random(3)
        game = make_game("S")
        endings = [choose_word(game, difficulty, rng)[-1] for _ in range(200)]
        return sum(letter_ease(WORDS, e) < -1 for e in endings) / len(endings)

    shares = {name: awkward_share(d) for name, d in DIFFICULTIES.items()}
    assert shares["impossible"] > shares["hard"] > shares["medium"] > shares["easy"]


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
    difficulty = custom_difficulty(min_length=5, max_length=9, mean_length=7)
    first = choose_word(game, difficulty, random.Random(42))
    assert choose_word(game, difficulty, random.Random(42)) == first


def test_typing_delays_cover_each_letter_and_enter():
    delays = typing_delays("apple", random.Random(0), thinking=2.0)
    assert len(delays) == len("apple") + 1
    assert all(delay > 0 for delay in delays)
    assert delays[0] >= 2.0  # includes time to think of the word


def challenge_game(letter, words, bonus_test, round_bonus=NO_ROUND_BONUS):
    game = ChallengeGame([Player("Ann"), Player("Bob")], words, rng=random.Random(0))
    game.letter = letter
    game.challenge = ANY_WORD
    game.round_bonus = round_bonus
    game.bonus = Challenge("test bonus", bonus_test)
    game.multiplier = 2.0
    return game


def test_goes_for_the_bonus_as_often_as_its_difficulty_says():
    game = challenge_game("A", WordList(["apple", "axe", "avocado"]), lambda word: "x" in word)
    always = custom_difficulty(bonus_chance=1)
    never = custom_difficulty(bonus_chance=0)
    rng = random.Random(0)

    assert {choose_word(game, always, rng) for _ in range(20)} == {"axe"}
    assert {choose_word(game, never, rng) for _ in range(50)} >= {"apple", "avocado"}


def test_plays_any_word_when_the_bonus_is_out_of_reach():
    game = challenge_game("A", WordList(["apple"]), lambda word: "z" in word)
    always = custom_difficulty(bonus_chance=1)
    assert choose_word(game, always, random.Random(0)) == "apple"


def test_goes_for_round_bonus_points_as_often_as_its_difficulty_says():
    per_z = RoundBonus("+5 per Z", lambda word: 5 * word.count("z"))
    words = WordList(["amaze", "azalea", "apple", "arrow", "axle", "album", "angel"])
    game = challenge_game("A", words, lambda word: False, per_z)
    always = custom_difficulty(round_bonus_chance=1)
    never = custom_difficulty(round_bonus_chance=0)
    rng = random.Random(0)

    assert {choose_word(game, always, rng) for _ in range(30)} == {"amaze", "azalea"}
    assert len({choose_word(game, never, rng) for _ in range(100)}) >= 5


def test_round_bonus_hunting_keeps_the_top_quarter():
    per_e = RoundBonus("+1 per E", lambda word: word.count("e"))
    words = ["excellence", "eerie", "exceed", "eel", "east", "echo", "elk", "ego"]
    game = challenge_game("E", WordList(words), lambda word: False, per_e)
    assert most_round_points(game, words) == ["excellence", "eerie", "exceed"]
    assert most_round_points(game, ["echo", "elk"]) == ["echo", "elk"]  # all earn the same
    game.round_bonus = NO_ROUND_BONUS
    assert most_round_points(game, words) == words  # nothing to hunt for


def test_thinks_longer_in_challenge_mode_and_longest_for_the_bonus():
    words = WordList(["apple", "axe"])
    classic = make_game("A", words)
    challenge = challenge_game("A", words, lambda word: "x" in word)
    medium = DIFFICULTIES["medium"]

    def average(game, word):
        rng = random.Random(0)
        return sum(thinking_time(game, medium, word, rng) for _ in range(400)) / 400

    factor = math.exp(-EASE_THINKING * letter_ease(words, "A"))
    assert average(classic, "apple") == pytest.approx(medium.thinking * factor, rel=0.1)
    assert average(challenge, "apple") == pytest.approx(medium.challenge_thinking * factor, rel=0.1)
    assert average(challenge, "axe") == pytest.approx(
        (medium.challenge_thinking + 3) * factor, rel=0.1
    )


def test_thinking_time_varies_like_a_persons():
    game = make_game("A")
    rng = random.Random(0)
    times = [thinking_time(game, DIFFICULTIES["medium"], "apple", rng) for _ in range(400)]
    assert min(times) < 0.7 * DIFFICULTIES["medium"].thinking
    assert max(times) > 1.5 * DIFFICULTIES["medium"].thinking


def test_typing_speed_sets_the_pause_between_letters():
    rng = random.Random(0)
    slow = typing_delays("abcdefghij" * 10, rng, thinking=0, letter_time=0.3)
    fast = typing_delays("abcdefghij" * 10, rng, thinking=0, letter_time=0.1)
    assert sum(slow[:-1]) / 100 == pytest.approx(0.3, rel=0.15)
    assert sum(fast[:-1]) / 100 == pytest.approx(0.1, rel=0.15)


@pytest.mark.parametrize("game_type", [Game, ChallengeGame])
def test_harder_computers_score_more_per_turn(game_type):
    def average_points(difficulty):
        rng = random.Random(0)
        game = game_type([Player("Ann"), Player("Bob")], WORDS, rng=random.Random(0))
        points = []
        for letter in "STECRDPB":
            game.letter = letter
            if isinstance(game, ChallengeGame):
                game.challenge = ANY_WORD
                game.round_bonus = game._pick_round_bonus()
            for _ in range(25):
                word = choose_word(game, difficulty, rng)
                thinking = thinking_time(game, difficulty, word, rng)
                seconds = sum(typing_delays(word, rng, thinking, difficulty.typing))
                points.append(game.score(word, seconds))
        return sum(points) / len(points)

    points = [average_points(d) for d in DIFFICULTIES.values()]
    assert points == sorted(points)
    for chance in ("bonus_chance", "round_bonus_chance"):
        chances = [getattr(d, chance) for d in DIFFICULTIES.values()]
        assert chances == sorted(chances)


def test_challenge_mode_can_shorten_the_computers_words():
    words = WordList.default()
    shorter = custom_difficulty(
        min_length=8, max_length=10, mean_length=9, challenge_length_shift=-4
    )

    def average_length(game_type):
        rng = random.Random(0)
        game = game_type([Player("Ann"), Player("Bob")], words, rng=random.Random(0))
        game.letter = "S"
        if game_type is ChallengeGame:
            game.challenge = ANY_WORD
        return sum(len(choose_word(game, shorter, rng)) for _ in range(60)) / 60

    assert average_length(ChallengeGame) < average_length(Game) - 3
