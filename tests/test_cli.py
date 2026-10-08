import random

import pytest

from shiritori import __version__, cli
from shiritori.computer import DIFFICULTIES, ComputerPlayer
from shiritori.game import Game, Player
from shiritori.terminal import TurnPrompt
from shiritori.words import WordList


@pytest.fixture
def answers(monkeypatch):
    """Feed scripted answers to input() and record the prompts it was given."""
    prompts = []

    def feed(*lines):
        remaining = list(lines)

        def fake_input(prompt=""):
            prompts.append(prompt)
            return remaining.pop(0)

        monkeypatch.setattr("builtins.input", fake_input)
        return prompts

    return feed


def test_parse_args_defaults():
    args = cli.parse_args([])
    assert args.target_score == 100
    assert args.turn_time == 10


def test_parse_args_custom_values():
    args = cli.parse_args(["--target-score", "50", "--turn-time", "20"])
    assert args.target_score == 50
    assert args.turn_time == 20


@pytest.mark.parametrize("value", ["0", "-5", "ten", "2.5"])
def test_parse_args_rejects_bad_numbers(value, capsys):
    with pytest.raises(SystemExit):
        cli.parse_args(["--target-score", value])
    assert "expected a whole number above zero" in capsys.readouterr().err


def test_version(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.parse_args(["--version"])
    assert exit_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_one_player_faces_the_computer(answers):
    answers("1", "Neer", "3")
    players = cli.ask_players()

    assert [player.name for player in players] == ["Neer", "Computer"]
    assert not isinstance(players[0], ComputerPlayer)
    assert isinstance(players[1], ComputerPlayer)
    assert players[1].difficulty is DIFFICULTIES["hard"]


def test_several_players_play_each_other(answers):
    answers("3", "Ann", "Bob", "Cat")
    players = cli.ask_players()

    assert [player.name for player in players] == ["Ann", "Bob", "Cat"]
    assert not any(isinstance(player, ComputerPlayer) for player in players)


def test_blank_answers_use_the_defaults(answers):
    answers("", "", "")
    players = cli.ask_players()

    assert [player.name for player in players] == ["Player 1", "Computer"]
    assert players[1].difficulty is DIFFICULTIES["easy"]


def test_reprompts_after_invalid_answers(answers, capsys):
    prompts = answers("0", "11", "two", "2", "computer", "Ann", "ANN", "x" * 21, "Bob")
    players = cli.ask_players()

    assert [player.name for player in players] == ["Ann", "Bob"]
    assert len(prompts) == 9
    output = capsys.readouterr().out
    assert "Enter a number from 1 to 10." in output
    assert "'Computer' is reserved for the computer." in output
    assert "'ANN' is already playing." in output
    assert "Keep names to 20 characters or fewer." in output


@pytest.mark.parametrize(
    ("answer", "expected"), [("2", "medium"), ("Impossible", "impossible"), ("", "easy")]
)
def test_ask_difficulty_by_number_or_name(answers, answer, expected):
    answers(answer)
    assert cli.ask_difficulty() is DIFFICULTIES[expected]


def test_ask_difficulty_reprompts(answers, capsys):
    answers("5", "expert", "hard")
    assert cli.ask_difficulty() is DIFFICULTIES["hard"]
    assert capsys.readouterr().out.count("Choose 1-4 or type a difficulty name.") == 2


def test_play_runs_until_someone_wins(monkeypatch, capsys):
    monkeypatch.setattr(cli, "typing_delays", lambda word, rng: [0.0] * (len(word) + 1))
    players = [ComputerPlayer("Hal"), ComputerPlayer("Eve", difficulty=DIFFICULTIES["hard"])]
    game = Game(players, WordList.default(), target_score=60, rng=random.Random(1))

    winner = cli.play(game, random.Random(2))

    assert winner.score >= 60
    assert [player for player in players if player.score >= 60] == [winner]
    output = capsys.readouterr().out
    assert "First to 60 points wins." in output
    assert f"Hal: {players[0].score} | Eve: {players[1].score}" in output


def test_play_with_people_at_the_keyboard(monkeypatch, capsys):
    typed = list("xyz\n\x7f\x7f\x7fapple\negg\ngiraffe\n")

    class ScriptedPrompt(TurnPrompt):
        def read_word(self, check):
            return super().read_word(check, lambda: typed.pop(0))

    monkeypatch.setattr(cli, "TurnPrompt", ScriptedPrompt)
    words = WordList(["apple", "egg", "giraffe"])
    game = Game([Player("Ann"), Player("Bob")], words, target_score=30)
    game.letter = "A"

    winner = cli.play(game)

    assert winner.name == "Ann"
    assert typed == []
    output = capsys.readouterr().out
    assert "xyz  (must start with A)" in output
    assert "Ann (A): apple  +15" in output
    assert "Bob (E): egg  +13" in output
    assert "Ann (G): giraffe  +17" in output


def test_main_needs_a_terminal(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert cli.main([]) == 1
    assert "interactive terminal" in capsys.readouterr().err


def test_main_says_goodbye_on_ctrl_c(monkeypatch, capsys):
    def interrupt(prompt=""):
        raise KeyboardInterrupt

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", interrupt)
    assert cli.main([]) == 130
    assert "Thanks for playing!" in capsys.readouterr().out


def test_main_plays_a_whole_game(monkeypatch, capsys):
    winner = Player("Ann", score=104)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(cli, "ask_players", lambda: [winner, Player("Bob")])
    monkeypatch.setattr(cli, "play", lambda game: winner)

    assert cli.main([]) == 0
    assert "Ann wins with 104 points!" in capsys.readouterr().out
