import random

import pytest

from shiritori.game import STARTING_LETTERS, Game, Move, Player
from shiritori.words import WordList

WORDS = WordList(["apple", "egg", "eagle", "giraffe", "elephant", "tiger", "rabbit"])


def make_game(*names, letter="A", **options):
    players = [Player(name) for name in names or ("Ann", "Bob")]
    game = Game(players, WORDS, rng=random.Random(0), **options)
    game.letter = letter
    return game


def test_needs_at_least_two_players():
    with pytest.raises(ValueError):
        Game([Player("Ann")], WORDS)


def test_starts_with_a_friendly_letter():
    for seed in range(50):
        game = Game([Player("Ann"), Player("Bob")], WORDS, rng=random.Random(seed))
        assert game.letter in STARTING_LETTERS


@pytest.mark.parametrize(
    ("word", "problem"),
    [
        ("", "use at least 3 letters"),
        ("ap", "use at least 3 letters"),
        ("egg", "must start with A"),
        ("aardvark", "not in the dictionary"),
    ],
)
def test_check_word_explains_the_problem(word, problem):
    assert make_game().check_word(word) == problem


def test_check_word_accepts_a_valid_word_in_any_case():
    game = make_game()
    assert game.check_word("apple") is None
    assert game.check_word("APPLE") is None


def test_check_word_rejects_words_already_played():
    game = make_game(letter="E")
    game.play("egg", seconds=1)
    game.letter = "E"
    assert game.check_word("egg") == "already played"


def test_play_scores_the_word_and_passes_the_turn():
    game = make_game()
    points = game.play("Apple", seconds=2)

    assert points == 5 + 10 - 2
    assert game.players[0].score == points
    assert game.used_words == {"apple"}
    assert game.moves == [Move(game.players[0], "apple", points)]
    assert game.letter == "E"
    assert game.current_player is game.players[1]


def test_play_rejects_invalid_words_without_changing_anything():
    game = make_game()
    with pytest.raises(ValueError, match="must start with A"):
        game.play("egg", seconds=1)
    assert game.players[0].score == 0
    assert game.used_words == set()
    assert game.current_player is game.players[0]


@pytest.mark.parametrize(
    ("seconds", "points"),
    [(0, 15), (2.4, 13), (2.6, 12), (10, 5), (14, 1), (20, -5)],
)
def test_score_is_word_length_plus_seconds_left(seconds, points):
    assert make_game().score("apple", seconds) == points


def test_turn_time_sets_the_bonus():
    assert make_game(turn_time=30).score("apple", seconds=5) == 30


def test_turns_rotate_through_every_player():
    game = make_game("Ann", "Bob", "Cat")
    order = []
    for word in ["apple", "egg", "giraffe", "elephant"]:
        order.append(game.current_player.name)
        game.play(word, seconds=0)
    assert order == ["Ann", "Bob", "Cat", "Ann"]


def test_the_round_is_played_out_before_anyone_wins():
    game = make_game(target_score=30)
    game.play("apple", seconds=0)  # Ann: 15
    game.play("egg", seconds=0)  # Bob: 13
    assert not game.final_round
    game.play("giraffe", seconds=0)  # Ann: 32, but Bob hasn't had his second turn
    assert game.final_round
    assert not game.round_complete
    assert game.winner is None
    game.play("elephant", seconds=0)  # Bob: 31
    assert game.round_complete
    assert game.winner is game.players[0]


def test_the_last_player_can_still_win_the_round():
    game = make_game(target_score=30)
    game.players[1].score = 5
    for word in ("apple", "egg", "giraffe", "elephant"):  # Ann: 32, Bob: 5 + 13 + 18 = 36
        game.play(word, seconds=0)
    assert game.winner is game.players[1]


def test_a_tie_for_the_lead_plays_another_round():
    game = make_game(target_score=30)
    game.players[1].score = 1
    for word in ("apple", "egg", "giraffe", "elephant"):  # Ann: 32, Bob: 1 + 13 + 18 = 32
        game.play(word, seconds=0)
    assert game.round_complete
    assert game.final_round
    assert game.winner is None
    game.play("tiger", seconds=0)  # Ann: 47
    assert game.winner is None
    game.play("rabbit", seconds=0)  # Bob: 48
    assert game.winner is game.players[1]


def test_everyone_gets_the_same_number_of_turns():
    game = make_game("Ann", "Bob", "Cat", target_score=10)
    game.play("apple", seconds=0)  # Ann already has enough to win
    assert game.winner is None
    game.play("egg", seconds=0)
    assert game.winner is None
    game.play("giraffe", seconds=0)  # Cat: 17
    assert game.winner is game.players[2]


def test_skip_passes_the_turn_with_a_new_letter():
    game = make_game(letter="Z")
    game.skip()
    assert game.current_player is game.players[1]
    assert game.letter in STARTING_LETTERS
    assert game.players[0].score == 0


def test_classic_games_have_a_ten_second_clock_and_no_bonuses():
    game = make_game()
    assert game.mode == "classic"
    assert game.turn_time == 10
    assert game.multiplier_for("apple") == 1.0
    game.play("apple", seconds=0)
    assert game.moves[-1].multiplier == 1.0
