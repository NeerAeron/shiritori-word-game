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
from .challenges import ChallengeGame
from .computer import (
    DIFFICULTIES,
    ComputerPlayer,
    Difficulty,
    choose_word,
    thinking_time,
    typing_delays,
)
from .game import DEFAULT_TARGET_SCORE, MIN_WORD_LENGTH, Game, Player
from .stats import Stats, StatsError, counts_toward_stats, format_stats, stats_file
from .terminal import BANNER, Keyboard, TurnPrompt
from .words import WordList

PROGRAM = "python play.py"
MAX_PLAYERS = 10
MAX_NAME_LENGTH = 20
COMPUTER_NAME = "Computer"
GAME_TYPES: dict[str, type[Game]] = {"classic": Game, "challenge": ChallengeGame}

RULES = f"""\
how to play:
  Take turns naming a word that starts with the last letter of the previous
  word. Words must be in the dictionary, at least {MIN_WORD_LENGTH} letters long, and can
  only be played once per game.

  Each word scores one point per letter plus a time bonus: the seconds left
  on the turn clock. Once the clock runs out, the bonus becomes a penalty.
  The first player to reach the target score wins.

  In challenge mode, every word must also meet a challenge that changes each
  turn, like "end with S" or "no letter E". Words that also meet the game's
  bonus challenge have their points multiplied.

  Your record, high scores, and favorite words are saved in stats.json in
  the game folder. Games with a custom --target-score or --turn-time don't
  count toward them.

  Play alone against the computer, or with up to {MAX_PLAYERS} people sharing one
  keyboard. Press Ctrl+C at any time to quit.
"""

T = TypeVar("T")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
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
        metavar="SECONDS",
        help=(
            f"seconds on the clock each turn (default: {Game.default_turn_time}, "
            f"or {ChallengeGame.default_turn_time} in challenge mode)"
        ),
    )
    stats = parser.add_mutually_exclusive_group()
    stats.add_argument(
        "--stats", action="store_true", help="show your records, high scores, and word stats"
    )
    stats.add_argument("--reset-stats", action="store_true", help="erase all your stats")
    parser.add_argument("--version", action="version", version=f"Shiritori {__version__}")
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


def _choose(prompt: str, options: Sequence[str]) -> str:
    """Ask the player to pick one of *options* by number or name; the first is the default."""
    menu = "  ".join(f"{number}) {option}" for number, option in enumerate(options, 1))

    def parse(answer: str) -> str:
        if answer.lower() in options:
            return answer.lower()
        number = _to_int(answer or "1")
        if number is None or not 1 <= number <= len(options):
            raise ValueError(f"Choose 1-{len(options)} or type one of the names.")
        return options[number - 1]

    return ask(f"{prompt}: {menu} [1]: ", parse)


def ask_game_type() -> type[Game]:
    """Ask whether to play classic or challenge mode."""
    return GAME_TYPES[_choose("Mode", list(GAME_TYPES))]


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
    return DIFFICULTIES[_choose("Difficulty", list(DIFFICULTIES))]


def scoreboard(players: Sequence[Player]) -> str:
    return " | ".join(f"{player.name}: {player.score}" for player in players)


def intro(game: Game) -> str:
    """Explain the rules that matter for this game."""
    rules = (
        f"First to {game.target_score} points wins. Words score a point per letter, "
        f"plus a point for every second left on the {game.turn_time}-second clock "
        "(or minus one for every second over)."
    )
    if not isinstance(game, ChallengeGame):
        return textwrap.fill(rules, 72)
    challenge = (
        "Challenge mode: every word must also meet a challenge, which changes every "
        "turn. Vowels are A, E, I, O, and U."
    )
    bonus = (
        f"Bonus challenge for this game: {game.bonus.text}. Words that do this too "
        f"score x{game.multiplier:g}!"
    )
    return "\n\n".join(textwrap.fill(text, 72) for text in (challenge, rules, bonus))


def play(game: Game, rng: random.Random | None = None, keyboard: Keyboard | None = None) -> Player:
    """Run turns until someone reaches the target score, and return the winner."""
    rng = rng or random.Random()
    keyboard = keyboard or Keyboard()
    print(f"\n{intro(game)}\n")
    with keyboard:
        while (winner := game.winner) is None:
            player = game.current_player
            label = f"{player.name} ({game.letter})"
            if isinstance(game, ChallengeGame):
                print(
                    f"  Challenge: {game.challenge.text}"
                    f"   [x{game.multiplier:g} bonus: {game.bonus.text}]"
                )

            if isinstance(player, ComputerPlayer):
                word = choose_word(game, player.difficulty, rng)
                if word is None:
                    game.skip()
                    print(f"{player.name} is stumped! The new letter is {game.letter}.")
                    continue
                thinking = thinking_time(game, player.difficulty, word, rng)
                with TurnPrompt(label, game.turn_time) as prompt:
                    seconds = prompt.type_word(word, typing_delays(word, rng, thinking))
            else:
                keyboard.discard_pending()
                with TurnPrompt(label, game.turn_time) as prompt:
                    word, seconds = prompt.read_word(game.check_word, keyboard.read_key)

            points = game.play(word, seconds)
            bonus = game.moves[-1].multiplier
            print(f"{label}: {word}  {points:+d}" + (f"  (x{bonus:g} bonus!)" if bonus > 1 else ""))
            print(f"    {scoreboard(game.players)}")
    return winner


def record_stats(game: Game, path: Path) -> None:
    """Add a finished game to the saved stats, and announce anything new."""
    if not counts_toward_stats(game):
        print("Games with custom rules don't count toward your stats.")
        return
    try:
        stats = Stats.load(path)
        report = stats.record_game(game, date.today())
        stats.save(path)
    except StatsError as error:
        print(f"Your stats weren't updated. {error}")
        return

    if report.high_score_ranks:
        rank = report.high_score_ranks[0]
        best = stats.high_scores[game.mode][rank - 1]
        print(
            f"New {game.mode} high score #{rank}: "
            f"{best.player} scored {best.points} with {best.word!r}!"
        )
    if report.longest_word:
        word = report.longest_word
        print(f"New longest word: {word!r} ({len(word)} letters)!")
    for player in game.players:
        if isinstance(player, ComputerPlayer):
            record = stats.records[game.mode][player.difficulty.name]
            print(
                f"Your {game.mode} record against {player.difficulty.name}: "
                f"{record.won} won, {record.lost} lost."
            )
    print(f"See all your stats with: {PROGRAM} --stats")


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
    path = stats_file()
    if args.stats:
        return show_stats(path)
    if args.reset_stats:
        return reset_stats(path)
    if not sys.stdin.isatty():
        print("Shiritori needs an interactive terminal to play in.", file=sys.stderr)
        return 1

    print(BANNER)
    try:
        game_type = ask_game_type()
        players = ask_players()
        game = game_type(
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
    record_stats(game, path)
    return 0
