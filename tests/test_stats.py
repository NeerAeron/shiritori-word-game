import json
from datetime import date
from pathlib import Path

import pytest

from shiritori import stats as stats_module
from shiritori.computer import DIFFICULTIES, ComputerPlayer
from shiritori.game import Game, Player
from shiritori.stats import (
    HIGH_SCORE_COUNT,
    MULTIPLAYER,
    HighScore,
    Record,
    Stats,
    StatsError,
    counts_toward_stats,
    default_path,
    format_stats,
)
from shiritori.words import WordList

TODAY = date(2026, 10, 8)
WORDS = WordList(["apple", "egg", "giraffe", "elephant", "tiger", "rabbit"])


def finished_game(players, plays, **options):
    """Play *plays* (word, seconds) in order, starting from A, until someone wins."""
    game = Game(players, WORDS, target_score=30, **options)
    game.letter = "A"
    for word, seconds in plays:
        game.play(word, seconds)
    assert game.winner is not None
    return game


def human_beats_computer(difficulty="medium"):
    you = Player("Neer")
    computer = ComputerPlayer("Computer", difficulty=DIFFICULTIES[difficulty])
    # Neer: apple 15 + giraffe 17 = 32. Computer: egg 13.
    return finished_game([you, computer], [("apple", 0), ("egg", 0), ("giraffe", 0)])


def computer_beats_human(difficulty="medium"):
    computer = ComputerPlayer("Computer", difficulty=DIFFICULTIES[difficulty])
    you = Player("Neer")
    # Computer: apple 15 + giraffe 17 = 32. Neer: egg 13.
    return finished_game([computer, you], [("apple", 0), ("egg", 0), ("giraffe", 0)])


def test_counts_wins_and_losses_per_difficulty():
    stats = Stats()
    stats.record_game(human_beats_computer("medium"), TODAY)
    stats.record_game(human_beats_computer("medium"), TODAY)
    stats.record_game(computer_beats_human("medium"), TODAY)
    stats.record_game(computer_beats_human("hard"), TODAY)

    assert stats.vs_computer["medium"] == Record(played=3, won=2)
    assert stats.vs_computer["medium"].lost == 1
    assert stats.vs_computer["hard"] == Record(played=1, won=0)
    assert "easy" not in stats.vs_computer
    assert stats.multiplayer_games == 0


def test_counts_multiplayer_games_separately():
    stats = Stats()
    game = finished_game([Player("Ann"), Player("Bob")], [("apple", 0), ("egg", 0), ("giraffe", 0)])
    stats.record_game(game, TODAY)

    assert stats.multiplayer_games == 1
    assert stats.vs_computer == {}
    assert {entry.mode for entry in stats.high_scores} == {MULTIPLAYER}


def test_high_scores_hold_your_best_words_not_the_computers():
    stats = Stats()
    ranks = stats.record_game(human_beats_computer(), TODAY)

    assert stats.high_scores == [
        HighScore(17, "giraffe", "Neer", "medium", "2026-10-08"),
        HighScore(15, "apple", "Neer", "medium", "2026-10-08"),
    ]
    assert ranks == [1, 2]


def test_high_scores_keep_only_the_best_and_older_ties_first():
    stats = Stats(
        high_scores=[HighScore(20 - n, f"old{n}", "Ann", "easy", "2025-01-01") for n in range(10)]
    )
    # Neer's new words score 17 and 15; old scores run 20 down to 11.
    ranks = stats.record_game(human_beats_computer(), TODAY)

    assert len(stats.high_scores) == HIGH_SCORE_COUNT
    assert [entry.points for entry in stats.high_scores] == [20, 19, 18, 17, 17, 16, 15, 15, 14, 13]
    assert stats.high_scores[3].word == "old3"  # the older 17 stays ahead
    assert stats.high_scores[4].word == "giraffe"
    assert ranks == [5, 8]


def test_reports_no_ranks_when_nothing_makes_the_list():
    stats = Stats(high_scores=[HighScore(50, "word", "Ann", "easy", "2025-01-01")] * 10)
    assert stats.record_game(human_beats_computer(), TODAY) == []


def test_refuses_unfinished_games():
    game = Game([Player("Ann"), Player("Bob")], WORDS)
    with pytest.raises(ValueError):
        Stats().record_game(game, TODAY)


def test_only_standard_rules_count():
    players = [Player("Ann"), Player("Bob")]
    assert counts_toward_stats(Game(players, WORDS))
    assert not counts_toward_stats(Game(players, WORDS, target_score=50))
    assert not counts_toward_stats(Game(players, WORDS, turn_time=30))


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "nested" / "stats.json"
    stats = Stats()
    stats.record_game(human_beats_computer(), TODAY)
    stats.save(path)

    assert Stats.load(path) == stats
    assert json.loads(path.read_text())["version"] == 1
    assert not path.with_name("stats.json.tmp").exists()


def test_load_starts_fresh_without_a_file(tmp_path):
    assert Stats.load(tmp_path / "missing.json") == Stats()


@pytest.mark.parametrize(
    "contents",
    [
        "not json",
        "[]",
        '{"version": 2, "vs_computer": {}, "multiplayer_games": 0, "high_scores": []}',
        '{"version": 1, "vs_computer": {"easy": {"played": "x", "won": 0}},'
        ' "multiplayer_games": 0, "high_scores": []}',
        '{"version": 1}',
    ],
)
def test_load_rejects_bad_files(tmp_path, contents):
    path = tmp_path / "stats.json"
    path.write_text(contents)
    with pytest.raises(StatsError):
        Stats.load(path)


def test_save_reports_errors(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")
    with pytest.raises(StatsError):
        Stats().save(blocker / "stats.json")


def test_default_path_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setenv("SHIRITORI_STATS_FILE", str(tmp_path / "custom.json"))
    assert default_path() == tmp_path / "custom.json"


def test_default_path_is_the_project_folder_in_a_clone(monkeypatch, tmp_path):
    monkeypatch.delenv("SHIRITORI_STATS_FILE")
    (tmp_path / "pyproject.toml").write_text("")
    monkeypatch.setattr(stats_module, "PROJECT_FOLDER", tmp_path)
    assert default_path() == tmp_path / "stats.json"


def test_stats_file_is_gitignored():
    gitignore = Path(__file__).parent.parent / ".gitignore"
    assert "stats.json" in gitignore.read_text().splitlines()


@pytest.mark.parametrize(
    ("platform", "env", "expected"),
    [
        ("linux", {}, Path("/home/neer/.local/share/shiritori/stats.json")),
        ("linux", {"XDG_DATA_HOME": "/data"}, Path("/data/shiritori/stats.json")),
        ("darwin", {}, Path("/home/neer/Library/Application Support/shiritori/stats.json")),
        ("win32", {"APPDATA": "/appdata"}, Path("/appdata/shiritori/stats.json")),
    ],
)
def test_installed_copies_use_the_platform_data_folder(
    monkeypatch, tmp_path, platform, env, expected
):
    monkeypatch.delenv("SHIRITORI_STATS_FILE")
    monkeypatch.setattr(stats_module, "PROJECT_FOLDER", tmp_path)  # no pyproject.toml here
    for name in ("XDG_DATA_HOME", "APPDATA"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(stats_module.sys, "platform", platform)
    monkeypatch.setattr(Path, "home", lambda: Path("/home/neer"))
    assert default_path() == expected


def test_format_stats_with_no_games():
    report = format_stats(Stats())
    assert "  easy             0    0     0         -" in report
    assert "Multiplayer games: 0" in report
    assert "None yet" in report


def test_format_stats_shows_records_and_high_scores():
    stats = Stats()
    stats.record_game(human_beats_computer("hard"), TODAY)
    stats.record_game(computer_beats_human("hard"), TODAY)
    report = format_stats(stats).splitlines()

    assert "  hard             2    1     1       50%" in report
    assert "  #  Points  Word     Player  Mode  Date" in report
    assert "  1      17  giraffe  Neer    hard  2026-10-08" in report
