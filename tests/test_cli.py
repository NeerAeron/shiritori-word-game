import random

import pytest

from shiritori import __version__, cli
from shiritori.challenges import NO_ROUND_BONUS, Challenge, ChallengeGame, RoundBonus
from shiritori.computer import DIFFICULTIES, ComputerPlayer
from shiritori.game import Game, Move, Player
from shiritori.stats import HighScore, Record, Stats
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


class FakeKeyboard:
    """Types out a script of keys instead of reading a real keyboard."""

    def __init__(self, keys=""):
        self.keys = list(keys)
        self.discarded = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        pass

    def discard_pending(self):
        self.discarded += 1

    def read_key(self):
        return self.keys.pop(0)


@pytest.fixture
def instant_computer(monkeypatch):
    """Make the computer type instantly."""
    monkeypatch.setattr(cli, "thinking_time", lambda game, difficulty, word, rng: 0.0)
    monkeypatch.setattr(
        cli, "typing_delays", lambda word, rng, thinking, letter_time: [0.0] * (len(word) + 1)
    )


def test_parse_args_defaults():
    args = cli.parse_args([])
    assert args.target_score is None  # each mode has its own default
    assert args.turn_time is None  # each mode has its own default


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


@pytest.mark.parametrize(
    ("answer", "game_type"),
    [
        ("", Game),
        ("1", Game),
        ("classic", Game),
        ("2", ChallengeGame),
        ("Challenge", ChallengeGame),
    ],
)
def test_ask_game_type(answers, answer, game_type):
    answers(answer)
    assert cli.ask_game_type() is game_type


def test_one_player_faces_the_computer(answers):
    answers("1", "Neer", "4")
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
    assert players[1].difficulty is DIFFICULTIES["beginner"]


def test_reprompts_after_invalid_answers(answers, capsys):
    prompts = answers("0", "5", "two", "2", "computer", "Ann", "ANN", "x" * 21, "Bob")
    players = cli.ask_players()

    assert [player.name for player in players] == ["Ann", "Bob"]
    assert len(prompts) == 9
    output = capsys.readouterr().out
    assert "Enter a number from 1 to 4." in output
    assert "'Computer' is reserved for the computer." in output
    assert "'ANN' is already playing." in output
    assert "Keep names to 20 characters or fewer." in output


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("1", "beginner"), ("3", "medium"), ("Impossible", "impossible"), ("", "beginner")],
)
def test_ask_difficulty_by_number_or_name(answers, answer, expected):
    answers(answer)
    assert cli.ask_difficulty() is DIFFICULTIES[expected]


def test_ask_difficulty_reprompts(answers, capsys):
    answers("6", "expert", "hard")
    assert cli.ask_difficulty() is DIFFICULTIES["hard"]
    assert capsys.readouterr().out.count("Choose 1-5 or type one of the names.") == 2


@pytest.mark.parametrize("game_type", [Game, ChallengeGame])
def test_computers_play_until_someone_wins(instant_computer, capsys, game_type):
    players = [ComputerPlayer("Hal"), ComputerPlayer("Eve", difficulty=DIFFICULTIES["hard"])]
    game = game_type(players, WordList.default(), target_score=60, rng=random.Random(1))

    winner = cli.play(game, random.Random(2), FakeKeyboard(), sleep=lambda seconds: None)

    assert winner.score >= 60
    assert winner.score == max(player.score for player in players)
    assert game.round_complete  # both players had the same number of turns
    output = capsys.readouterr().out
    assert f"Hal: {players[0].score} | Eve: {players[1].score}" in output
    assert ("Challenge:" in output) == (game_type is ChallengeGame)


def test_play_with_people_at_the_keyboard(capsys):
    keyboard = FakeKeyboard("xyz\n\x7f\x7f\x7fpple\ngg\niraffe\nlephant\n")
    words = WordList(["apple", "egg", "giraffe", "elephant"])
    game = Game([Player("Ann"), Player("Bob")], words, target_score=30)
    game.letter = "A"

    winner = cli.play(game, keyboard=keyboard)

    assert winner.name == "Ann"
    assert keyboard.keys == []
    assert keyboard.discarded == 4  # before each person's turn
    output = capsys.readouterr().out
    assert "Axyz  (not in the dictionary)" in output  # the A is typed for you
    assert "Ann (A): apple  +15  (5L + 10s)" in output
    assert "Bob (E): egg  +13" in output
    assert "Ann (G): giraffe  +17" in output
    assert "Ann reached 30! Last round." in output
    assert "Bob (E): elephant  +18" in output  # Bob still gets his turn: 31 to Ann's 32


def test_a_tie_for_the_lead_plays_another_round(capsys):
    keyboard = FakeKeyboard("apple\negg\ngiraffe\nelephant\ntiger\nrabbit\n")
    words = WordList(["apple", "egg", "giraffe", "elephant", "tiger", "rabbit"])
    game = Game([Player("Ann"), Player("Bob", score=1)], words, target_score=30)
    game.letter = "A"

    winner = cli.play(game, keyboard=keyboard)

    assert winner.name == "Bob"  # 32 all after two rounds, then 47 to 48
    output = capsys.readouterr().out
    assert "Tied! One more round." in output
    assert "Bob (R): rabbit  +16" in output


def test_challenge_mode_with_people_at_the_keyboard(monkeypatch, capsys):
    end_with_e = Challenge("end with E", lambda word: word.endswith("e"))
    per_l = RoundBonus("+3 per L", lambda word: 3 * word.count("l"))
    monkeypatch.setattr(ChallengeGame, "_pick_challenge", lambda self: end_with_e)
    monkeypatch.setattr(ChallengeGame, "_pick_round_bonus", lambda self: per_l)
    keyboard = FakeKeyboard("nt\n\x7f\x7fpple\nagle\ndge\nlse\n")
    words = WordList(["ant", "apple", "eagle", "edge", "else"])
    game = ChallengeGame([Player("Ann"), Player("Bob")], words, target_score=40)
    game.letter = "A"
    game.bonus, game.multiplier = Challenge("include G", lambda word: "g" in word), 2.0

    winner = cli.play(game, keyboard=keyboard, sleep=lambda seconds: None)

    assert winner.name == "Bob"  # 53 to 46, thanks to his last turn
    output = capsys.readouterr().out
    assert "GAME BONUS x2: include G" in output
    assert "Starting in 1..." in output
    assert "  Challenge: end with E | +3 per L | x2: include G" in output
    assert "+10 | Ann: Apple" in output  # the countdown shows time points
    assert "Ant  (doesn't meet the challenge)" in output
    assert "Ann (A): apple  +18  (5L + 3B + 10s)\n" in output
    assert "Bob (E): eagle  +36  (5L + 3B + 10s) x2" in output
    assert "Ann (E): edge  +28  (4L + 10s) x2" in output
    assert "Bob (E): else  +17  (4L + 3B + 10s)\n" in output


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


@pytest.fixture
def quick_game(monkeypatch):
    """Skip setup and play: Ann has already won a classic game against Bob."""
    winner = Player("Ann", score=104)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(cli, "ask_game_type", lambda: Game)
    monkeypatch.setattr(cli, "ask_players", lambda: [winner, Player("Bob")])
    monkeypatch.setattr(cli, "play", lambda game: winner)


def test_main_plays_a_whole_game(quick_game, capsys):
    assert cli.main([]) == 0
    assert "Ann wins with 104 points!" in capsys.readouterr().out


def test_main_saves_stats_in_the_game_folder(quick_game, stats_file):
    cli.main([])
    assert Stats.load(stats_file).multiplayer_games == {"classic": 1}


def finished_game_vs_computer(game_type=Game, **rules):
    """A finished game in which Neer played apple and giraffe and beat the computer."""
    neer = Player("Neer")
    computer = ComputerPlayer("Computer", difficulty=DIFFICULTIES["hard"])
    game = game_type([neer, computer], WordList(["apple", "egg", "giraffe"]), **rules)
    for word in ["apple", "egg", "giraffe"]:
        game.letter = word[0].upper()
        if isinstance(game, ChallengeGame):
            game.challenge = Challenge("any", lambda word: True)
            game.round_bonus = NO_ROUND_BONUS
            game.multiplier = 1.0
        game.play(word, seconds=0)
    game.skip()  # the computer passes, finishing the round
    neer.score = game.target_score + 4  # skip ahead to Neer winning
    return game


def test_record_stats_saves_the_game_and_announces_news(stats_file, capsys):
    cli.record_stats(finished_game_vs_computer(), stats_file)

    stats = Stats.load(stats_file)
    assert stats.records["classic"]["hard"] == Record(played=1, won=1)
    assert [entry.word for entry in stats.high_scores["classic"]] == ["giraffe", "apple"]
    assert stats.words == {"apple": 1, "giraffe": 1}
    output = capsys.readouterr().out
    assert "New high score #1: giraffe (17)" in output
    assert "Record vs hard: 1 won, 0 lost" in output
    assert "New longest word" not in output  # nothing to beat yet
    assert f"All stats: {cli.program_name()} --stats" in output


def test_record_stats_announces_a_new_longest_word(stats_file, capsys):
    Stats(words={"egg": 1}).save(stats_file)
    cli.record_stats(finished_game_vs_computer(ChallengeGame), stats_file)

    output = capsys.readouterr().out
    assert "New longest word: giraffe" in output
    assert "Record vs hard: 1 won, 0 lost" in output
    assert Stats.load(stats_file).records["challenge"]["hard"] == Record(played=1, won=1)


def test_record_stats_skips_games_with_custom_rules(stats_file, capsys):
    cli.record_stats(finished_game_vs_computer(target_score=50), stats_file)

    assert not stats_file.exists()
    assert "isn't in your stats" in capsys.readouterr().out


def test_record_stats_survives_a_broken_stats_file(stats_file, capsys):
    stats_file.write_text("not json")
    cli.record_stats(finished_game_vs_computer(), stats_file)

    assert stats_file.read_text() == "not json"
    assert "Stats not saved." in capsys.readouterr().out


def test_stats_flag_prints_the_report(stats_file, capsys):
    Stats(
        records={"classic": {"easy": Record(played=4, won=3)}},
        high_scores={"challenge": [HighScore(52, "quiz", "Neer", "easy", "2026-10-08")]},
        words={"quiz": 2, "zebra": 1},
    ).save(stats_file)

    assert cli.main(["--stats"]) == 0
    output = capsys.readouterr().out
    assert "75%" in output
    assert "Favorite word             quiz (played 2 times)" in output
    assert "Challenge high scores" in output
    assert str(stats_file) in output


def test_stats_flag_reports_a_broken_file(stats_file, capsys):
    stats_file.write_text("not json")
    assert cli.main(["--stats"]) == 1
    assert "Couldn't read" in capsys.readouterr().err


def test_stats_flags_cant_be_combined():
    with pytest.raises(SystemExit):
        cli.parse_args(["--stats", "--reset-stats"])


@pytest.mark.parametrize(
    ("answer", "erased"), [("y", True), ("YES", True), ("", False), ("n", False)]
)
def test_reset_stats_asks_first(answers, stats_file, answer, erased):
    Stats(multiplayer_games={"classic": 3}).save(stats_file)
    answers(answer)

    assert cli.main(["--reset-stats"]) == 0
    assert stats_file.exists() is not erased


def test_reset_stats_with_nothing_to_erase(stats_file, capsys):
    assert cli.main(["--reset-stats"]) == 0
    assert "no stats to erase" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("script", "name"),
    [
        ("/home/neer/shiritori/play.py", "python play.py"),
        ("/home/neer/shiritori/shiritori/__main__.py", "python -m shiritori"),
        ("/home/neer/.local/bin/shiritori", "shiritori"),
    ],
)
def test_program_name_matches_how_the_game_was_started(monkeypatch, script, name):
    monkeypatch.setattr("sys.argv", [script])
    assert cli.program_name() == name


def test_challenges_follow_the_computers_difficulty():
    args = cli.parse_args([])
    you_vs_hard = [
        Player("Neer"),
        ComputerPlayer("Computer", difficulty=DIFFICULTIES["impossible"]),
    ]
    assert cli.new_game(ChallengeGame, you_vs_hard, args).difficulty == "impossible"
    people = [Player("Ann"), Player("Bob")]
    assert cli.new_game(ChallengeGame, people, args).difficulty == "hard"
    assert type(cli.new_game(Game, people, args)) is Game


def test_rules_flag_explains_how_to_play(capsys):
    assert cli.main(["--rules"]) == 0
    output = capsys.readouterr().out
    assert "How to play" in output
    assert "Challenge mode" in output
    assert "up to 4 people" in output
    assert "150 in challenge mode" in output
    assert "start at +10 and drop 1 every 2" in output


def test_instructions_only_show_when_asked_for(capsys):
    game = Game([Player("Ann"), Player("Bob")], WordList(["apple", "egg"]), target_score=10)
    game.letter = "A"
    cli.play(game, keyboard=FakeKeyboard("apple\negg\n"))
    output = capsys.readouterr().out
    assert "How to play" not in output
    assert "points to win" not in output


def test_challenge_mode_shows_the_bonus_then_counts_down(capsys):
    game = ChallengeGame([Player("Ann"), Player("Bob")], WordList.default(), rng=random.Random(0))
    pauses = []
    cli.show_bonus(game, sleep=pauses.append)
    output = capsys.readouterr().out
    assert f"GAME BONUS x{game.multiplier:g}: {game.bonus.text}" in output
    assert [line for line in output.split("\r") if "Starting in" in line] == [
        f"  Starting in {n}..." for n in (5, 4, 3, 2, 1)
    ]
    assert pauses == [1] * 5


@pytest.mark.parametrize(
    ("move", "text"),
    [
        (Move(Player("Neer"), "restitution", 17, time_bonus=6), "(11L + 6s)"),
        (Move(Player("Neer"), "tiger", 2, time_bonus=-3), "(5L - 3s)"),
        (Move(Player("Neer"), "kiosks", 17, time_bonus=8, round_bonus=3), "(6L + 3B + 8s)"),
        (Move(Player("Neer"), "dusty", 37, 2.3, 9, 2), "(5L + 2B + 9s) x2.3"),
    ],
)
def test_breakdown_shows_how_the_points_add_up(move, text):
    assert cli.breakdown(move) == text
