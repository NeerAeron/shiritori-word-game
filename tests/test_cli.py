import random
import re

import pytest

from shiritori import __version__, cli, style
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
    assert f"      Hal {players[0].score} · Eve {players[1].score}\n" in output
    assert ("REQ:" in output) == (game_type is ChallengeGame)
    assert "\x1b" not in output  # no colors when the output isn't a terminal


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
    assert "+15 | Ann: Apple  (5L + 10s)\n      Ann 15 · Bob 0\n" in output
    assert "+13 | Bob: Egg" in output
    assert "+17 | Ann: Giraffe" in output
    assert "» Ann reached 30! Last round." in output
    assert "+18 | Bob: Elephant" in output  # Bob still gets his turn: 31 to Ann's 32


def test_a_tie_for_the_lead_plays_another_round(capsys):
    keyboard = FakeKeyboard("apple\negg\ngiraffe\nelephant\ntiger\nrabbit\n")
    words = WordList(["apple", "egg", "giraffe", "elephant", "tiger", "rabbit"])
    game = Game([Player("Ann"), Player("Bob", score=1)], words, target_score=30)
    game.letter = "A"

    winner = cli.play(game, keyboard=keyboard)

    assert winner.name == "Bob"  # 32 all after two rounds, then 47 to 48
    output = capsys.readouterr().out
    assert "» Tied! One more round." in output
    assert "+16 | Bob: Rabbit" in output


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
    assert "Challenge mode: playing to 40 points\nGAME BONUS x2: include G\n" in output
    assert "Starting in 1..." in output
    assert "\nREQ: end with E | +3 per L, x2: include G\n" in output
    assert "+10 | Ann: Apple" in output  # the countdown shows time points
    assert "Ant  (doesn't meet the REQ)" in output
    assert "+18 | Ann: Apple  (5L + 3B + 10s)\n" in output
    assert "+36 | Bob: Eagle  (5L + 3B + 10s) x2\n" in output
    assert "+28 | Ann: Edge  (4L + 10s) x2\n" in output
    assert "+17 | Bob: Else  (4L + 3B + 10s)\n" in output


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
    assert "  New high score #1: Giraffe (17)" in output
    assert "  New best game: 16 points a word" in output
    assert "Record vs hard: 1 won, 0 lost" in output
    assert "New longest word" not in output  # nothing to beat yet
    assert f"All stats: {cli.program_name()} --stats" in output


def test_record_stats_announces_a_new_longest_word(stats_file, capsys):
    Stats(words={"egg": 1}).save(stats_file)
    cli.record_stats(finished_game_vs_computer(ChallengeGame), stats_file)

    output = capsys.readouterr().out
    assert "  New longest word: Giraffe" in output
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
        f"Starting in {n}..." for n in (5, 4, 3, 2, 1)
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


@pytest.mark.parametrize(
    ("game_type", "elapsed", "tone"),
    [
        (Game, 0, None),
        (Game, 6, None),  # 4 seconds left
        (Game, 7, "yellow"),
        (Game, 9.5, "yellow"),
        (Game, 10, "red"),
        (Game, 12, "red"),
        (ChallengeGame, 0, None),
        (ChallengeGame, 14, None),  # +3
        (ChallengeGame, 16, "yellow"),  # +2
        (ChallengeGame, 22, "yellow"),  # 0, in the grace period
        (ChallengeGame, 25, "red"),  # -1
    ],
)
def test_the_countdown_turns_yellow_then_red(game_type, elapsed, tone):
    game = game_type([Player("Ann"), Player("Bob")], WordList.default(), rng=random.Random(0))
    assert cli.countdown_tone(game)(elapsed) == tone


def challenge_turn(challenge, round_bonus=None, bonus="include Q", multiplier=1.9):
    game = ChallengeGame([Player("Ann"), Player("Bob")], WordList.default(), rng=random.Random(0))
    game.challenge = Challenge(challenge, lambda word: True)
    game.round_bonus = round_bonus or RoundBonus("+8 per X", lambda word: 0)
    game.bonus, game.multiplier = Challenge(bonus, lambda word: False), multiplier
    return game


def test_the_requirement_and_bonuses_share_a_line():
    game = challenge_turn("end with N", bonus="four consonants in a row")
    assert cli.requirement_lines(game) == [
        "REQ: end with N | +8 per X, x1.9: four consonants in a row"
    ]
    game.round_bonus = NO_ROUND_BONUS
    assert cli.requirement_lines(game) == ["REQ: end with N | x1.9: four consonants in a row"]


def test_a_long_requirement_puts_the_bonuses_on_their_own_line():
    animal = "hide an animal (ANT, BAT, CAT, COW, DOG, HEN, OWL, PIG, RAT)"
    game = challenge_turn(
        animal, RoundBonus("+4 per vowel pair", lambda word: 0), "two double letters"
    )
    lines = cli.requirement_lines(game)
    assert lines == [
        f"REQ: {animal}",
        "     +4 per vowel pair, x1.9: two double letters",
    ]
    assert all(len(line) <= 79 for line in lines)


def test_the_requirement_line_picks_out_what_the_bonuses_are_for():
    style.use_colors(True)
    line = cli.requirement_lines(challenge_turn("no E", bonus="O is the only vowel"))[0]
    assert line == (
        "\x1b[1mREQ: no E\x1b[0m \x1b[2m|\x1b[0m "
        "+8 per \x1b[35mX\x1b[0m, x1.9: \x1b[35mO is the only vowel\x1b[0m"
    )
    animal = "hide an animal (ANT, BAT, CAT, COW, DOG, HEN, OWL, PIG, RAT)"
    vowel_pair = RoundBonus("+4 per vowel pair", lambda word: 0)
    second = cli.requirement_lines(challenge_turn(animal, vowel_pair))[1]
    assert second.startswith("     +4 per \x1b[35mvowel pair\x1b[0m, x1.9: ")


def test_the_scoreboard_lists_everyone_in_seating_order():
    players = [Player("Neer", 12), Player("Computer", 0)]
    assert cli.scoreboard(players) == "      Neer 12 · Computer 0"
    style.use_symbols(False)
    assert cli.scoreboard(players) == "      Neer 12 | Computer 0"


@pytest.mark.parametrize(
    ("scores", "bold"),
    [((12, 0, 5), [12]), ((12, 12, 5), [12, 12]), ((7, 7, 7), [])],
)
def test_the_scoreboard_shows_the_leaders_in_bold(scores, bold):
    style.use_colors(True)
    board = cli.scoreboard([Player(name, score) for name, score in zip("ABC", scores, strict=True)])
    assert [int(n) for n in re.findall(r"\x1b\[1m(\d+)\x1b\[0m", board)] == bold


def test_a_long_scoreboard_wraps_under_the_names():
    players = [Player(f"{name * 18}{n}", 100 + n) for n, name in enumerate("ABCD")]
    lines = cli.scoreboard(players).split("\n")
    assert len(lines) == 2
    assert all(line.startswith("      ") and len(line) <= 79 for line in lines)
    assert lines[0].endswith(" ·")


@pytest.mark.parametrize("columns", ["80", "50", "40"])
def test_a_wrapped_scoreboard_never_runs_past_the_edge(monkeypatch, columns):
    monkeypatch.setenv("COLUMNS", columns)
    names = [("A" * 20, 100), ("B" * 20, 101), ("C" * 15, 102), ("Dot", 5)]
    for count in range(2, 5):
        for cut in range(1, 21):
            players = [Player(name[:cut] or name, score) for name, score in names[:count]]
            for line in cli.scoreboard(players).split("\n"):
                assert len(line) <= style.line_width()


def test_breakdown_colors_only_the_multiplier():
    style.use_colors(True)
    move = Move(Player("Neer"), "dusty", 37, 1.9, 9, 2)
    assert cli.breakdown(move) == "\x1b[2m(5L + 2B + 9s)\x1b[0m \x1b[35mx1.9\x1b[0m"


@pytest.mark.parametrize(
    ("points", "start"),
    [(22, "\x1b[32m+22\x1b[0m"), (-4, "\x1b[31m -4\x1b[0m"), (0, " +0")],
)
def test_result_lines_color_the_points(points, start):
    style.use_colors(True)
    line = cli.result_line(Move(Player("Neer"), "fort", points, time_bonus=points - 4))
    assert line.startswith(start + " \x1b[2m|\x1b[0m Neer: \x1b[1mFort\x1b[0m  ")


@pytest.mark.parametrize(
    ("winner", "mark"), [(Player("Neer"), "32"), (ComputerPlayer("Computer"), "2")]
)
def test_the_winner_mark_only_celebrates_people(capsys, winner, mark):
    style.use_colors(True)
    cli.show_winner(winner)
    assert capsys.readouterr().out.startswith(f"\n\x1b[{mark}m»\x1b[0m \x1b[1m{winner.name} wins")


def test_rules_headings_are_bold_only_with_colors():
    assert "\x1b" not in cli.rules()
    style.use_colors(True)
    assert "\x1b[1mHow to play\x1b[0m" in cli.rules()
    assert "\x1b[1mChallenge mode\x1b[0m" in cli.rules()
    assert "  Name a word" in cli.rules()
