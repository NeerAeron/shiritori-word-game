"""Command-line entry point: game setup and the turn loop."""

from __future__ import annotations

import argparse
import random
import sys
import textwrap
from collections.abc import Callable, Sequence
from typing import TypeVar

from . import __version__
from .computer import DIFFICULTIES, ComputerPlayer, Difficulty, choose_word, typing_delays
from .game import MIN_WORD_LENGTH, Game, Player
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
        default=100,
        metavar="POINTS",
        help="points needed to win (default: %(default)s)",
    )
    parser.add_argument(
        "--turn-time",
        type=_positive_int,
        default=10,
        metavar="SECONDS",
        help="seconds on the clock each turn (default: %(default)s)",
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


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
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
    return 0
