"""Command-line entry point: game setup and the turn loop."""

from __future__ import annotations

import argparse
import random
import sys
import textwrap
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import TypeVar

from . import __version__
from .computer import DIFFICULTIES, ComputerPlayer, Difficulty, choose_word, typing_delays
from .game import DEFAULT_TARGET_SCORE, DEFAULT_TURN_TIME, MIN_WORD_LENGTH, Game, Player
from .stats import Stats, StatsError, counts_toward_stats, default_path, format_stats
from .terminal import BANNER, TurnPrompt
from .words import WordList

MAX_PLAYERS = 10
MAX_NAME_LENGTH = 20
COMPUTER_NAME = "Computer"

RULES = f"""\
how to play:
  Take turns naming a word that starts with the last letter of the previous
  word. Words must be in the dictionary, at least {MIN_WORD_LENGTH} letters long, and can
  only be played once per game.

  Each word scores one point per letter plus a time bonus: the seconds left
  on the turn clock. Once the clock runs out, the bonus becomes a penalty.
  The first player to reach the target score wins.

  Your record against each difficulty and your highest-scoring words are
  saved between games. Games with a custom --target-score or --turn-time
  don't count toward them.

  Play alone against the computer, or with up to {MAX_PLAYERS} people sharing one
  keyboard. Press Ctrl+C at any time to quit.
"""

T = TypeVar("T")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="shiritori",
        description="Play Shiritori, the word-chain game, in your terminal.",
        epilog=RULES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--target-score",
        type=_positive_int,
        default=DEFAULT_TARGET_SCORE,
        metavar="POINTS",
        help="points needed to win (default: %(default)s)",
    )
    parser.add_argument(
        "--turn-time",
        type=_positive_int,
        default=DEFAULT_TURN_TIME,
        metavar="SECONDS",
        help="seconds on the clock each turn (default: %(default)s)",
    )
    stats = parser.add_mutually_exclusive_group()
    stats.add_argument(
        "--stats", action="store_true", help="show your record and high scores, then exit"
    )
    stats.add_argument(
        "--reset-stats", action="store_true", help="erase your record and high scores"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def _positive_int(value: str) -> int:
    number = _to_int(value)
    if number is None or number < 1:
        raise argparse.ArgumentTypeError(f"expected a whole number above zero, got {value!r}")
    return number


def _to_int(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def ask(prompt: str, parse: Callable[[str], T]) -> T:
    """Prompt until *parse* accepts the answer; *parse* raises ValueError to reject it."""
    while True:
        try:
            return parse(input(prompt).strip())
        except ValueError as error:
            print(error)


def ask_players() -> list[Player]:
    """Ask who is playing. A lone player is matched against the computer."""

    def parse_count(answer: str) -> int:
        number = _to_int(answer or "1")
        if number is None or not 1 <= number <= MAX_PLAYERS:
            raise ValueError(f"Enter a number from 1 to {MAX_PLAYERS}.")
        return number

    count = ask(f"Number of players (1-{MAX_PLAYERS}) [1]: ", parse_count)
    players: list[Player] = []

    def parse_name(answer: str) -> str:
        name = answer or f"Player {len(players) + 1}"
        if len(name) > MAX_NAME_LENGTH:
            raise ValueError(f"Keep names to {MAX_NAME_LENGTH} characters or fewer.")
        if name.casefold() == COMPUTER_NAME.casefold():
            raise ValueError(f"{COMPUTER_NAME!r} is reserved for the computer.")
        if any(name.casefold() == player.name.casefold() for player in players):
            raise ValueError(f"{name!r} is already playing.")
        return name

    for number in range(1, count + 1):
        players.append(Player(ask(f"Player {number} name [Player {number}]: ", parse_name)))

    if count == 1:
        players.append(ComputerPlayer(COMPUTER_NAME, difficulty=ask_difficulty()))
    return players


def ask_difficulty() -> Difficulty:
    """Ask how strong the computer opponent should be."""
    names = list(DIFFICULTIES)
    menu = "  ".join(f"{number}) {name}" for number, name in enumerate(names, 1))

    def parse(answer: str) -> Difficulty:
        if answer.lower() in DIFFICULTIES:
            return DIFFICULTIES[answer.lower()]
        number = _to_int(answer or "1")
        if number is None or not 1 <= number <= len(names):
            raise ValueError(f"Choose 1-{len(names)} or type a difficulty name.")
        return DIFFICULTIES[names[number - 1]]

    return ask(f"Difficulty: {menu} [1]: ", parse)


def scoreboard(players: Sequence[Player]) -> str:
    return " | ".join(f"{player.name}: {player.score}" for player in players)


def play(game: Game, rng: random.Random | None = None) -> Player:
    """Run turns until someone reaches the target score, and return the winner."""
    rng = rng or random.Random()
    intro = (
        f"First to {game.target_score} points wins. Words score a point per letter, "
        f"plus a point for every second left on the {game.turn_time}-second clock "
        "(or minus one for every second over)."
    )
    print(f"\n{textwrap.fill(intro, 72)}\n")
    while (winner := game.winner) is None:
        player = game.current_player
        label = f"{player.name} ({game.letter})"

        if isinstance(player, ComputerPlayer):
            word = choose_word(game, player.difficulty, rng)
            if word is None:
                game.skip()
                print(f"{player.name} is stumped! The new letter is {game.letter}.")
                continue
            with TurnPrompt(label, game.turn_time) as prompt:
                seconds = prompt.type_word(word, typing_delays(word, rng))
        else:
            with TurnPrompt(label, game.turn_time) as prompt:
                word, seconds = prompt.read_word(game.check_word)

        points = game.play(word, seconds)
        print(f"{label}: {word}  {points:+d}")
        print(f"    {scoreboard(game.players)}")
    return winner


def record_stats(game: Game, path: Path) -> None:
    """Add a finished game to the saved stats, and announce anything new."""
    if not counts_toward_stats(game):
        print("Games with custom rules don't count toward your stats.")
        return
    try:
        stats = Stats.load(path)
        ranks = stats.record_game(game, date.today())
        stats.save(path)
    except StatsError as error:
        print(f"Your stats weren't updated. {error}")
        return

    if ranks:
        best = stats.high_scores[ranks[0] - 1]
        print(f"New high score #{ranks[0]}: {best.player} scored {best.points} with {best.word!r}!")
    for player in game.players:
        if isinstance(player, ComputerPlayer):
            record = stats.vs_computer[player.difficulty.name]
            print(
                f"Your record against {player.difficulty.name}: "
                f"{record.won} won, {record.lost} lost."
            )
    print("See all your stats with: shiritori --stats")


def show_stats(path: Path) -> int:
    try:
        stats = Stats.load(path)
    except StatsError as error:
        print(error, file=sys.stderr)
        return 1
    print(format_stats(stats))
    print(f"\nStats file: {path}")
    return 0


def reset_stats(path: Path) -> int:
    if not path.exists():
        print("There are no stats to erase.")
        return 0
    try:
        answer = input(f"Erase all stats in {path}? [y/N]: ")
    except (KeyboardInterrupt, EOFError):
        answer = ""
        print()
    if answer.strip().lower() not in ("y", "yes"):
        print("Your stats were left alone.")
        return 0
    try:
        path.unlink()
    except OSError as error:
        print(f"Couldn't erase {path}: {error}", file=sys.stderr)
        return 1
    print("Stats erased.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    stats_path = default_path()
    if args.stats:
        return show_stats(stats_path)
    if args.reset_stats:
        return reset_stats(stats_path)
    if not sys.stdin.isatty():
        print("shiritori needs an interactive terminal to play in.", file=sys.stderr)
        return 1

    print(BANNER)
    try:
        players = ask_players()
        game = Game(
            players,
            WordList.default(),
            target_score=args.target_score,
            turn_time=args.turn_time,
        )
        winner = play(game)
    except (KeyboardInterrupt, EOFError):
        print("\nThanks for playing!")
        return 130

    print(f"\n{winner.name} wins with {winner.score} points!")
    record_stats(game, stats_path)
    return 0
