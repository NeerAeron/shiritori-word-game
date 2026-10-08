import json
import random
from datetime import date
from pathlib import Path

import pytest

from shiritori import stats as stats_module
from shiritori.challenges import ANY_WORD, ChallengeGame
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
    format_stats,
    stats_file,
)
from shiritori.words import WordList

TODAY = date(2026, 10, 8)
WORDS = WordList(["apple", "egg", "giraffe", "elephant", "tiger", "rabbit", "eagle"])


def finished_game(players, words=("apple", "egg", "giraffe"), game_type=Game):
    """Play *words* in order from the letter A, then skip ahead to the first player winning."""
    game = game_type(players, WORDS, rng=random.Random(0))
    game.letter = "A"
    for word in words:
        if isinstance(game, ChallengeGame):
            game.challenge = ANY_WORD
        game.play(word, seconds=0)
    while not game.round_complete:
        game.skip()
    players[0].score = max(players[0].score, game.target_score)
    return game


def you_beat_the_computer(difficulty="medium", game_type=Game):
    you = Player("Neer")
    computer = ComputerPlayer("Computer", difficulty=DIFFICULTIES[difficulty])
    return finished_game([you, computer], game_type=game_type)  # Neer: apple, giraffe


def the_computer_beats_you(difficulty="medium"):
    computer = ComputerPlayer("Computer", difficulty=DIFFICULTIES[difficulty])
    you = Player("Neer")
    return finished_game([computer, you])  # Neer: egg


def test_stats_live_next_to_play_py(tmp_path):
    assert stats_file() == tmp_path / "stats.json"
    assert (tmp_path / "play.py").is_file()


def test_installed_copies_keep_stats_in_their_package_folder(monkeypatch, tmp_path):
    package = tmp_path / "site-packages" / "shiritori"
    monkeypatch.setattr(stats_module, "PACKAGE_FOLDER", package)
    assert stats_file() == package / "stats.json"


def test_the_real_game_folder_holds_the_game():
    folder = Path(stats_module.__file__).resolve().parent.parent
    assert (folder / "play.py").is_file()
    assert (folder / "README.md").is_file()


def test_stats_file_is_gitignored():
    gitignore = Path(__file__).parent.parent / ".gitignore"
    assert "stats.json" in gitignore.read_text().splitlines()


def test_counts_wins_and_losses_per_mode_and_difficulty():
    stats = Stats()
    stats.record_game(you_beat_the_computer("medium"), TODAY)
    stats.record_game(you_beat_the_computer("medium"), TODAY)
    stats.record_game(the_computer_beats_you("medium"), TODAY)
    stats.record_game(you_beat_the_computer("hard", game_type=ChallengeGame), TODAY)

    assert stats.records["classic"]["medium"] == Record(played=3, won=2)
    assert stats.records["classic"]["medium"].lost == 1
    assert stats.records["challenge"] == {"hard": Record(played=1, won=1)}
    assert stats.multiplayer_games == {}


def test_counts_multiplayer_games_per_mode():
    stats = Stats()
    stats.record_game(finished_game([Player("Ann"), Player("Bob")]), TODAY)

    assert stats.multiplayer_games == {"classic": 1}
    assert stats.records == {}
    assert {entry.opponent for entry in stats.high_scores["classic"]} == {MULTIPLAYER}


def test_high_scores_hold_your_best_words_not_the_computers():
    stats = Stats()
    report = stats.record_game(you_beat_the_computer(), TODAY)

    assert stats.high_scores["classic"] == [
        HighScore(17, "giraffe", "Neer", "medium", "2026-10-08"),
        HighScore(15, "apple", "Neer", "medium", "2026-10-08"),
    ]
    assert report.high_score_ranks == [1, 2]


def test_each_mode_has_its_own_high_scores():
    stats = Stats()
    stats.record_game(you_beat_the_computer(), TODAY)
    stats.record_game(you_beat_the_computer(game_type=ChallengeGame), TODAY)

    assert [entry.word for entry in stats.high_scores["classic"]] == ["giraffe", "apple"]
    assert [entry.word for entry in stats.high_scores["challenge"]] == ["giraffe", "apple"]
    assert stats.high_scores["challenge"][0].points >= 27  # 7 letters + a 20-second clock


def test_high_scores_keep_only_the_best_and_older_ties_first():
    old = [HighScore(20 - n, f"old{n}", "Ann", "easy", "2025-01-01") for n in range(10)]
    stats = Stats(high_scores={"classic": old})
    report = stats.record_game(you_beat_the_computer(), TODAY)  # 17 and 15

    scores = stats.high_scores["classic"]
    assert len(scores) == HIGH_SCORE_COUNT
    assert [entry.points for entry in scores] == [20, 19, 18, 17, 17, 16, 15, 15, 14, 13]
    assert scores[3].word == "old3"  # the older 17 stays ahead
    assert scores[4].word == "giraffe"
    assert report.high_score_ranks == [5, 8]


def test_keeps_count_of_every_word_people_play():
    stats = Stats()
    stats.record_game(you_beat_the_computer(), TODAY)  # Neer: apple, giraffe
    stats.record_game(the_computer_beats_you(), TODAY)  # Neer: egg
    stats.record_game(finished_game([Player("Ann"), Player("Bob")]), TODAY)  # all three

    assert stats.words == {"apple": 2, "giraffe": 2, "egg": 2}
    assert stats.words_played() == 6


def test_word_stats():
    stats = Stats(words={"apple": 2, "elephant": 1, "egg": 3, "tiger": 3, "eel": 1})

    assert stats.favorite_word() == ("egg", 3)  # tied with tiger, but played first
    assert stats.longest_word() == "elephant"
    assert stats.most_common_first_letter() == ("e", 5)
    assert stats.most_common_last_letter() == ("g", 3)  # ties with R go alphabetically


def test_word_stats_are_empty_before_any_games():
    stats = Stats()
    assert stats.favorite_word() is None
    assert stats.longest_word() is None
    assert stats.most_common_first_letter() is None
    assert stats.most_common_last_letter() is None


def test_reports_a_new_longest_word_but_not_the_first_one():
    stats = Stats()
    assert stats.record_game(you_beat_the_computer(), TODAY).longest_word is None

    game = finished_game([Player("Ann"), Player("Bob")], words=("apple", "elephant"))
    assert stats.record_game(game, TODAY).longest_word == "elephant"
    assert stats.record_game(you_beat_the_computer(), TODAY).longest_word is None


def test_refuses_unfinished_games():
    game = Game([Player("Ann"), Player("Bob")], WORDS)
    with pytest.raises(ValueError):
        Stats().record_game(game, TODAY)


def test_only_standard_rules_count():
    players = [Player("Ann"), Player("Bob")]
    assert counts_toward_stats(Game(players, WORDS))
    assert counts_toward_stats(ChallengeGame(players, WORDS))
    assert not counts_toward_stats(Game(players, WORDS, target_score=50))
    assert not counts_toward_stats(Game(players, WORDS, turn_time=20))
    assert not counts_toward_stats(ChallengeGame(players, WORDS, turn_time=10))


def test_save_and_load_round_trip(stats_file):
    stats = Stats()
    stats.record_game(you_beat_the_computer(), TODAY)
    multiplayer = finished_game([Player("Ann"), Player("Bob")], game_type=ChallengeGame)
    stats.record_game(multiplayer, TODAY)
    stats.save(stats_file)

    assert Stats.load(stats_file) == stats
    assert json.loads(stats_file.read_text())["version"] == 2
    assert not stats_file.with_name("stats.json.tmp").exists()


def test_load_starts_fresh_without_a_file(stats_file):
    assert Stats.load(stats_file) == Stats()


def test_load_upgrades_version_1_files(stats_file):
    entry = {"points": 21, "word": "quiz", "player": "Neer", "mode": "easy", "date": "2026-10-08"}
    version_1 = {
        "version": 1,
        "vs_computer": {"easy": {"played": 4, "won": 3}},
        "multiplayer_games": 2,
        "high_scores": [entry],
    }
    stats_file.write_text(json.dumps(version_1))
    stats = Stats.load(stats_file)

    assert stats.records == {"classic": {"easy": Record(played=4, won=3)}}
    assert stats.multiplayer_games == {"classic": 2}
    assert stats.high_scores == {"classic": [HighScore(21, "quiz", "Neer", "easy", "2026-10-08")]}
    assert stats.words == {}


@pytest.mark.parametrize(
    "contents",
    [
        "not json",
        "[]",
        '{"version": 3}',
        '{"version": 2, "records": {"classic": {"easy": {"played": "x", "won": 0}}},'
        ' "multiplayer_games": {}, "high_scores": {}, "words": {}}',
        '{"version": 2}',
        '{"version": 1}',
    ],
)
def test_load_rejects_bad_files(stats_file, contents):
    stats_file.write_text(contents)
    with pytest.raises(StatsError):
        Stats.load(stats_file)


def test_save_reports_errors(tmp_path):
    with pytest.raises(StatsError):
        Stats().save(tmp_path / "missing folder" / "stats.json")


def test_format_stats_before_any_games():
    report = format_stats(Stats())
    assert "None yet. Play a game to get started!" in report
    assert "  easy             0    0     0         -" in report
    assert "Multiplayer games: 0 classic, 0 challenge" in report
    assert report.count("None yet.") == 3  # words, plus each mode's high scores


def test_format_stats_shows_everything():
    stats = Stats(words={"apple": 2, "elephant": 1, "egg": 3})
    stats.record_game(you_beat_the_computer("hard"), TODAY)  # apple, giraffe
    stats.record_game(the_computer_beats_you("hard"), TODAY)  # egg
    report = format_stats(stats).splitlines()

    assert "  Words played              9" in report
    assert "  Favorite word             egg (played 4 times)" in report
    assert "  Longest word              elephant (8 letters)" in report
    assert "  Most common first letter  E (5 words)" in report
    assert "  Most common last letter   E (4 words)" in report
    assert "Classic mode against the computer" in report
    assert "  hard             2    1     1       50%" in report
    assert "Challenge mode against the computer" in report
    assert "  #  Points  Word     Player  Opponent  Date" in report
    assert "  1      17  giraffe  Neer    hard      2026-10-08" in report
