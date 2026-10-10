"""Command-line entry point: game setup and the turn loop."""

from __future__ import annotations

import argparse
import math
import random
import sys
import time
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path
from typing import TypeVar

from . import __version__
from .challenges import GRACE_SECONDS, NO_ROUND_BONUS, ChallengeGame
from .computer import (
    DIFFICULTIES,
    ComputerPlayer,
    Difficulty,
    choose_word,
    thinking_time,
    typing_delays,
)
from .game import MIN_WORD_LENGTH, Game, Move, Player
from .stats import Stats, StatsError, counts_toward_stats, format_stats, stats_file
from .style import (
    colors_supported,
    line_width,
    paint,
    plain,
    symbol,
    symbols_supported,
    use_colors,
    use_symbols,
    width,
)
from .terminal import BANNER, Keyboard, TurnPrompt
from .words import WordList

MAX_PLAYERS = 4
MAX_NAME_LENGTH = 20
COMPUTER_NAME = "Computer"
GAME_TYPES: dict[str, type[Game]] = {"classic": Game, "challenge": ChallengeGame}

CLASSIC_CLOCK = Game.default_turn_time
CHALLENGE_TIME_POINTS = ChallengeGame.default_turn_time // 2  # Time points as a turn starts
TARGET = Game.default_target_score
CHALLENGE_TARGET = ChallengeGame.default_target_score

HOW_TO_PLAY = f"""\
How to play

  Name a word that starts with the last letter of the previous word. That
  letter is filled in, so typing it is up to you; it turns bold if you do.
  Words must be real, {MIN_WORD_LENGTH}+ letters, and not already played this game.

  Score a point per letter, plus a point per second left on the
  {CLASSIC_CLOCK}-second clock. Run out of time and you lose points.
  "+13 | Neer: Tiger  (5L + 8s)" is 13 points: 5 letters, 8 seconds left.

  Reaching {TARGET} points ({CHALLENGE_TARGET} in challenge mode) ends the game once
  everyone has had the same number of turns. Highest score wins.

Challenge mode

  Every word must also meet the turn's requirement, like "REQ: end with S".
  Each turn has a round bonus too, like "+2 per S" (B in the score), and
  each game has a bonus, like "x2.5: include Q", that multiplies the points
  of words that meet it. Vowels are A, E, I, O, and U.

  Time points (the s in the score) start at +{CHALLENGE_TIME_POINTS} and drop 1 every 2
  seconds. At 0 there are {GRACE_SECONDS} seconds of grace, then they drop 1 a second.

Players

  Play the computer, or up to {MAX_PLAYERS} people on one keyboard. Ctrl+C quits.
"""

T = TypeVar("T")


def program_name() -> str:
    """The command the game was started with, for help and hints."""
    script = Path(sys.argv[0]).name
    if script == "play.py":
        return "python play.py"
    if script == "__main__.py":
        return "python -m shiritori"
    return "shiritori"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=program_name(),
        description="Play Shiritori, the word-chain game, in your terminal.",
        epilog=f"How to play: {program_name()} --rules",
    )
    parser.add_argument(
        "--target-score",
        type=_positive_int,
        metavar="POINTS",
        help=(
            f"points needed to win (default: {Game.default_target_score}, "
            f"or {ChallengeGame.default_target_score} in challenge mode)"
        ),
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
    stats.add_argument("--rules", action="store_true", help="explain how to play, then exit")
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
    # input() shows its prompt on stderr, which may not take colors even if stdout does.
    if not sys.stderr.isatty():
        prompt = plain(prompt)
    while True:
        try:
            return parse(input(prompt).strip())
        except ValueError as error:
            print(paint(str(error), "red"))


def _question(text: str, default: str) -> str:
    return f"{paint(text, 'bold')} {paint(f'[{default}]', 'dim')}: "


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

    return ask(f"{paint(prompt + ':', 'bold')} {menu} {paint('[1]', 'dim')}: ", parse)


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

    count = ask(_question(f"Number of players (1-{MAX_PLAYERS})", "1"), parse_count)
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
        players.append(
            Player(ask(_question(f"Player {number} name", f"Player {number}"), parse_name))
        )

    if count == 1:
        players.append(ComputerPlayer(COMPUTER_NAME, difficulty=ask_difficulty()))
    return players


def ask_difficulty() -> Difficulty:
    """Ask how strong the computer opponent should be."""
    return DIFFICULTIES[_choose("Difficulty", list(DIFFICULTIES))]


def capitalized(word: str) -> str:
    return word[:1].upper() + word[1:]


def event(message: str, mark_style: str = "yellow") -> str:
    """A line announcing something, such as the last round, marked so it stands out."""
    return f"{paint(symbol('»', '>'), mark_style)} {paint(message, 'bold')}"


def scoreboard(players: Sequence[Player]) -> str:
    """Everyone's score, such as "Neer 43 · Computer 34", with the leader in bold."""
    best = max(player.score for player in players)
    has_leader = len({player.score for player in players}) > 1

    def entry(player: Player) -> str:
        leads = has_leader and player.score == best
        return f"{player.name} {paint(str(player.score), 'bold') if leads else player.score}"

    entries = [entry(player) for player in players]
    separator = symbol(" · ", " | ")
    trail = separator.rstrip()  # Ends a line that continues below
    indent = " " * 6  # Under the names on the line above
    lines, line = [], entries[0]
    for position, entry in enumerate(entries[1:], 2):
        joined = line + paint(separator, "dim") + entry
        room_for_trail = len(trail) if position < len(entries) else 0
        if len(indent) + width(joined) + room_for_trail > line_width():
            lines.append(line + paint(trail, "dim"))
            line = entry
        else:
            line = joined
    lines.append(line)
    return "\n".join(indent + line for line in lines)


def breakdown(move: Move) -> str:
    """How a word's points add up, such as "(6L + 3B + 7s) x2.4".

    That's 6 letters, the round bonus, and the time points (in classic games,
    the seconds left), all times the game bonus.
    """
    parts = f"{len(move.word)}L"
    if move.round_bonus:
        parts += f" + {move.round_bonus}B"
    sign = "+" if move.time_bonus >= 0 else "-"
    text = paint(f"({parts} {sign} {abs(move.time_bonus)}s)", "dim")
    if move.multiplier > 1:
        text += " " + paint(f"x{move.multiplier:g}", "magenta")
    return text


def result_line(move: Move) -> str:
    """What a word scored, such as "+22 | Neer: Fort  (4L + 9s) x1.7"."""
    tone = "green" if move.points > 0 else "red" if move.points < 0 else None
    points = f"{move.points:+d}".rjust(3)
    word = paint(capitalized(move.word), "bold")
    return (
        f"{paint(points, tone) if tone else points} {paint('|', 'dim')} "
        f"{move.player.name}: {word}  {breakdown(move)}"
    )


def requirement_lines(game: ChallengeGame) -> list[str]:
    """The turn's requirement and bonuses, on one line if they fit.

    For example "REQ: no E | +3 per G, x1.9: O is the only vowel", with what
    each bonus is for (G, and O is the only vowel) picked out in color.
    """
    bonuses = []
    if game.round_bonus is not NO_ROUND_BONUS:
        amount, _, subject = game.round_bonus.text.partition(" per ")
        bonuses.append(f"{amount} per {paint(subject, 'magenta')}")
    bonuses.append(f"x{game.multiplier:g}: {paint(game.bonus.text, 'magenta')}")
    requirement = paint(f"REQ: {game.challenge.text}", "bold")
    one_line = f"{requirement} {paint('|', 'dim')} {', '.join(bonuses)}"
    if width(one_line) <= line_width():
        return [one_line]
    return [requirement, f"     {', '.join(bonuses)}"]


def show_header(game: Game) -> None:
    print()
    print(f"{paint(game.mode.title() + ' mode:', 'bold')} playing to {game.target_score} points")


def show_bonus(game: ChallengeGame, sleep: Callable[[float], None], seconds: int = 5) -> None:
    """Announce the game bonus, and give players a moment to read it."""
    print(
        f"{paint('GAME BONUS', 'bold')} x{game.multiplier:g}: {paint(game.bonus.text, 'magenta')}"
    )
    for left in range(seconds, 0, -1):
        print("\r" + paint(f"Starting in {left}...", "dim"), end="", flush=True)
        sleep(1)
    print("\r" + " " * len(f"Starting in {seconds}...") + "\r", end="", flush=True)


def countdown(game: Game) -> Callable[[float], str] | None:
    """What the turn countdown shows: time points in challenge mode, else the seconds left."""
    if isinstance(game, ChallengeGame):
        return lambda elapsed: f"{game.time_points(elapsed):+d}"
    return None


def countdown_tone(game: Game) -> Callable[[float], str | None]:
    """The countdown's color: yellow when time is nearly up, red once points are being lost."""
    if isinstance(game, ChallengeGame):

        def tone(elapsed: float) -> str | None:
            points = game.time_points(elapsed)
            return "red" if points < 0 else "yellow" if points <= 2 else None

    else:

        def tone(elapsed: float) -> str | None:
            left = math.ceil(game.turn_time - elapsed)
            return "red" if left <= 0 else "yellow" if left <= 3 else None

    return tone


def turn_prompt(game: Game) -> TurnPrompt:
    """The live prompt for the current player, with the word's first letter already typed."""
    return TurnPrompt(
        game.current_player.name,
        game.turn_time,
        start=game.letter,
        countdown=countdown(game),
        tone=countdown_tone(game),
    )


def play(
    game: Game,
    rng: random.Random | None = None,
    keyboard: Keyboard | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Player:
    """Run turns until the game has a winner, and return them."""
    rng = rng or random.Random()
    keyboard = keyboard or Keyboard()
    announced = False
    show_header(game)
    if isinstance(game, ChallengeGame):
        show_bonus(game, sleep)
    with keyboard:
        while (winner := game.winner) is None:
            print()
            player = game.current_player
            if isinstance(game, ChallengeGame):
                print("\n".join(requirement_lines(game)))

            if isinstance(player, ComputerPlayer):
                word = choose_word(game, player.difficulty, rng)
                if word is None:
                    game.skip()
                    print(event(f"{player.name} is stumped! New letter: {game.letter}"))
                    continue
                thinking = thinking_time(game, player.difficulty, word, rng)
                with turn_prompt(game) as prompt:
                    delays = typing_delays(word, rng, thinking, player.difficulty.typing)
                    seconds = prompt.type_word(word, delays)
            else:
                keyboard.discard_pending()
                with turn_prompt(game) as prompt:
                    word, seconds = prompt.read_word(game.check_word, keyboard.read_key)

            game.play(word, seconds)
            print(result_line(game.moves[-1]))
            print(scoreboard(game.players))

            if game.final_round and game.winner is None:
                if game.round_complete:
                    print(event("Tied! One more round."))
                elif not announced:
                    print(event(f"{player.name} reached {game.target_score}! Last round."))
                    announced = True
    return winner


def record_stats(game: Game, path: Path) -> None:
    """Add a finished game to the saved stats, and announce anything new."""
    # Indented to sit under the winner's name on the line above.
    if not counts_toward_stats(game):
        print("  " + paint("Custom rules, so this game isn't in your stats.", "dim"))
        return
    try:
        stats = Stats.load(path)
        report = stats.record_game(game, date.today())
        stats.save(path)
    except StatsError as error:
        print(f"  {paint('Stats not saved.', 'red')} {error}")
        return

    if report.high_score_ranks:
        rank = report.high_score_ranks[0]
        best = stats.high_scores[game.mode][rank - 1]
        label = paint(f"New high score #{rank}:", "green")
        print(f"  {label} {capitalized(best.word)} ({best.points})")
    if report.best_game:
        label = paint("New best game:", "green")
        print(f"  {label} {report.best_game.average:g} points a word")
    if report.longest_word:
        print(f"  {paint('New longest word:', 'green')} {capitalized(report.longest_word)}")
    for player in game.players:
        if isinstance(player, ComputerPlayer):
            record = stats.records[game.mode][player.difficulty.name]
            print(f"  Record vs {player.difficulty.name}: {record.won} won, {record.lost} lost")
    print("  " + paint(f"All stats: {program_name()} --stats", "dim"))


def show_stats(path: Path) -> int:
    try:
        stats = Stats.load(path)
    except StatsError as error:
        print(error, file=sys.stderr)
        return 1
    print(format_stats(stats))
    print("\n" + paint(f"Stats file: {path}", "dim"))
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


def new_game(game_type: type[Game], players: list[Player], args: argparse.Namespace) -> Game:
    rules = {"target_score": args.target_score, "turn_time": args.turn_time}
    if game_type is ChallengeGame:
        # Turn challenges follow the computer's difficulty. Games between people
        # use the challenge mode default.
        computer = next((p for p in players if isinstance(p, ComputerPlayer)), None)
        if computer:
            rules["difficulty"] = computer.difficulty.name
    return game_type(players, WordList.default(), **rules)


def rules() -> str:
    """How to play, with the headings in bold."""
    return "\n".join(
        paint(line, "bold") if line and not line.startswith(" ") else line
        for line in HOW_TO_PLAY.splitlines()
    )


def show_banner() -> None:
    for line in BANNER.splitlines():
        print(paint(line, "magenta"))
    print()
    print("The word-chain game, by Neer")
    print(paint(f"How to play: {program_name()} --rules", "dim"))
    print()


def show_winner(winner: Player) -> None:
    mark_style = "dim" if isinstance(winner, ComputerPlayer) else "green"
    print()
    print(event(f"{winner.name} wins with {winner.score} points!", mark_style))


def main(argv: Sequence[str] | None = None) -> int:
    use_colors(colors_supported(sys.stdout))
    use_symbols(symbols_supported(sys.stdout))
    args = parse_args(argv)
    path = stats_file()
    if args.rules:
        print(rules())
        return 0
    if args.stats:
        return show_stats(path)
    if args.reset_stats:
        return reset_stats(path)
    if not sys.stdin.isatty():
        print("Shiritori needs an interactive terminal to play in.", file=sys.stderr)
        return 1

    show_banner()
    try:
        game_type = ask_game_type()
        players = ask_players()
        game = new_game(game_type, players, args)
        winner = play(game)
    except (KeyboardInterrupt, EOFError):
        print("\nThanks for playing!")
        return 130

    show_winner(winner)
    record_stats(game, path)
    return 0
