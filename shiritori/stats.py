"""Saved stats: your record against the computer, high scores, and the words you play.

Stats are kept in stats.json in the game folder (the folder with README.md in
it) and nowhere else. .gitignore keeps the file out of version control.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .computer import DIFFICULTIES, ComputerPlayer
from .game import DEFAULT_TARGET_SCORE, Game

FORMAT_VERSION = 2
HIGH_SCORE_COUNT = 10
MODES = ("classic", "challenge")
MULTIPLAYER = "multiplayer"

# The folder the game lives in: the one that holds this package.
GAME_FOLDER = Path(__file__).resolve().parent.parent


def stats_file() -> Path:
    return GAME_FOLDER / "stats.json"


def counts_toward_stats(game: Game) -> bool:
    """Only games played with the standard rules count, so records stay comparable."""
    return game.target_score == DEFAULT_TARGET_SCORE and game.turn_time == game.default_turn_time


class StatsError(Exception):
    """The stats file couldn't be read or written."""


@dataclass
class Record:
    played: int = 0
    won: int = 0

    @property
    def lost(self) -> int:
        return self.played - self.won


@dataclass(frozen=True)
class HighScore:
    """A single word, ranked by the points it scored."""

    points: int
    word: str
    player: str
    opponent: str  # A difficulty name, or MULTIPLAYER
    date: str  # YYYY-MM-DD


@dataclass
class GameReport:
    """What a newly recorded game changed."""

    high_score_ranks: list[int]  # Ranks (from 1) its words reached in the high scores
    longest_word: str | None  # Set if it beat the previous longest word


@dataclass
class Stats:
    # Mode -> difficulty -> your record against the computer
    records: dict[str, dict[str, Record]] = field(default_factory=dict)
    # Mode -> number of games between people
    multiplayer_games: dict[str, int] = field(default_factory=dict)
    # Mode -> the best words, highest scoring first
    high_scores: dict[str, list[HighScore]] = field(default_factory=dict)
    # Every word people have played -> how many times, in the order first played
    words: dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Stats:
        """Read stats from *path*, or start fresh if it doesn't exist yet."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as error:
            raise StatsError(f"Couldn't read {path}: {error}") from error

        try:
            if data.get("version") == 1:
                data = _upgrade_from_version_1(data)
            if data.get("version") != FORMAT_VERSION:
                raise ValueError(f"unsupported version {data.get('version')!r}")
            return cls(
                records={
                    mode: {
                        name: Record(played=int(record["played"]), won=int(record["won"]))
                        for name, record in records.items()
                    }
                    for mode, records in data["records"].items()
                },
                multiplayer_games={
                    mode: int(count) for mode, count in data["multiplayer_games"].items()
                },
                high_scores={
                    mode: [
                        HighScore(
                            points=int(entry["points"]),
                            word=str(entry["word"]),
                            player=str(entry["player"]),
                            opponent=str(entry["opponent"]),
                            date=str(entry["date"]),
                        )
                        for entry in entries
                    ]
                    for mode, entries in data["high_scores"].items()
                },
                words={str(word): int(count) for word, count in data["words"].items()},
            )
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise StatsError(f"{path} isn't a valid stats file ({error}).") from error

    def save(self, path: Path) -> None:
        data = {
            "version": FORMAT_VERSION,
            "records": {
                mode: {name: asdict(record) for name, record in records.items()}
                for mode, records in self.records.items()
            },
            "multiplayer_games": self.multiplayer_games,
            "high_scores": {
                mode: [asdict(entry) for entry in entries]
                for mode, entries in self.high_scores.items()
            },
            "words": self.words,
        }
        # Write to a temporary file first so a crash can't leave a half-written file behind.
        temporary = path.with_name(path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        except OSError as error:
            raise StatsError(f"Couldn't save {path}: {error}") from error

    def record_game(self, game: Game, today: date) -> GameReport:
        """Add a finished game to the stats."""
        winner = game.winner
        if winner is None:
            raise ValueError("The game isn't over yet.")

        computer = next((p for p in game.players if isinstance(p, ComputerPlayer)), None)
        if computer:
            opponent = computer.difficulty.name
            record = self.records.setdefault(game.mode, {}).setdefault(opponent, Record())
            record.played += 1
            if winner is not computer:
                record.won += 1
        else:
            opponent = MULTIPLAYER
            self.multiplayer_games[game.mode] = self.multiplayer_games.get(game.mode, 0) + 1

        moves = [move for move in game.moves if not isinstance(move.player, ComputerPlayer)]
        previous_longest = self.longest_word()
        for move in moves:
            self.words[move.word] = self.words.get(move.word, 0) + 1
        longest = self.longest_word()

        plays = [
            HighScore(move.points, move.word, move.player.name, opponent, today.isoformat())
            for move in moves
        ]
        # Sorting is stable, so older entries keep their place ahead of new ties.
        ranked = sorted(
            self.high_scores.get(game.mode, []) + plays,
            key=lambda entry: entry.points,
            reverse=True,
        )[:HIGH_SCORE_COUNT]
        self.high_scores[game.mode] = ranked

        return GameReport(
            high_score_ranks=[
                rank for rank, entry in enumerate(ranked, 1) if any(entry is play for play in plays)
            ],
            longest_word=(
                longest
                if previous_longest and longest and len(longest) > len(previous_longest)
                else None
            ),
        )

    def words_played(self) -> int:
        return sum(self.words.values())

    def favorite_word(self) -> tuple[str, int] | None:
        """The word played most often and its count; ties go to the one played first."""
        return max(self.words.items(), key=lambda item: item[1], default=None)

    def longest_word(self) -> str | None:
        """The longest word played; ties go to the one played first."""
        return max(self.words, key=len, default=None)

    def most_common_first_letter(self) -> tuple[str, int] | None:
        return _most_common((word[0], count) for word, count in self.words.items())

    def most_common_last_letter(self) -> tuple[str, int] | None:
        return _most_common((word[-1], count) for word, count in self.words.items())


def _most_common(counts: Iterable[tuple[str, int]]) -> tuple[str, int] | None:
    """Total up (letter, count) pairs and return the top letter; ties go alphabetically."""
    totals: Counter[str] = Counter()
    for letter, count in counts:
        totals[letter] += count
    return min(totals.items(), key=lambda item: (-item[1], item[0]), default=None)


def _upgrade_from_version_1(data: dict) -> dict:
    """Version 1 had no challenge mode and didn't keep track of every word played."""
    return {
        "version": 2,
        "records": {"classic": data["vs_computer"]},
        "multiplayer_games": {"classic": data["multiplayer_games"]},
        "high_scores": {
            "classic": [{**entry, "opponent": entry["mode"]} for entry in data["high_scores"]]
        },
        "words": {},
    }


def format_stats(stats: Stats) -> str:
    lines = ["Your words"]
    favorite = stats.favorite_word()
    if favorite:
        word, count = favorite
        longest = stats.longest_word() or ""
        first, first_count = stats.most_common_first_letter() or ("", 0)
        last, last_count = stats.most_common_last_letter() or ("", 0)
        lines += _table(
            [
                "Words played",
                "Favorite word",
                "Longest word",
                "Most common first letter",
                "Most common last letter",
            ],
            [
                str(stats.words_played()),
                f"{word} ({_times(count)})",
                f"{longest} ({len(longest)} letters)",
                f"{first.upper()} ({_words(first_count)})",
                f"{last.upper()} ({_words(last_count)})",
            ],
        )
    else:
        lines.append("  None yet. Play a game to get started!")

    for mode in MODES:
        records = stats.records.get(mode, {})
        rows = []
        for name in DIFFICULTIES:
            record = records.get(name, Record())
            win_rate = f"{record.won / record.played:.0%}" if record.played else "-"
            rows.append([name, str(record.played), str(record.won), str(record.lost), win_rate])
        lines += ["", f"{mode.title()} mode against the computer"]
        lines += _columns(["Difficulty", "Played", "Won", "Lost", "Win rate"], rows, "<>>>>")

    multiplayer = ", ".join(f"{stats.multiplayer_games.get(mode, 0)} {mode}" for mode in MODES)
    lines += ["", f"Multiplayer games: {multiplayer}"]

    for mode in MODES:
        lines += ["", f"{mode.title()} high scores"]
        entries = stats.high_scores.get(mode, [])
        if entries:
            rows = [
                [str(rank), str(entry.points), entry.word, entry.player, entry.opponent, entry.date]
                for rank, entry in enumerate(entries, 1)
            ]
            lines += _columns(["#", "Points", "Word", "Player", "Opponent", "Date"], rows, ">><<<<")
        else:
            lines.append("  None yet.")
    return "\n".join(lines)


def _times(count: int) -> str:
    return "played once" if count == 1 else f"played {count} times"


def _words(count: int) -> str:
    return "1 word" if count == 1 else f"{count} words"


def _table(labels: Sequence[str], values: Sequence[str]) -> list[str]:
    width = max(map(len, labels))
    return [f"  {label.ljust(width)}  {value}" for label, value in zip(labels, values, strict=True)]


def _columns(header: Sequence[str], rows: Sequence[Sequence[str]], align: str) -> list[str]:
    """Lay out columns, each left- (<) or right-aligned (>) as *align* says."""
    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]
    lines = []
    for row in [header, *rows]:
        cells = [
            cell.ljust(width) if side == "<" else cell.rjust(width)
            for cell, width, side in zip(row, widths, align, strict=True)
        ]
        lines.append(("  " + "  ".join(cells)).rstrip())
    return lines
