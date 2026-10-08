"""Lifetime stats, saved between games: your record against each difficulty and high scores."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .computer import DIFFICULTIES, ComputerPlayer
from .game import DEFAULT_TARGET_SCORE, DEFAULT_TURN_TIME, Game

FORMAT_VERSION = 1
HIGH_SCORE_COUNT = 10
MULTIPLAYER = "multiplayer"

# The folder above the package: the repository root when running from a clone.
PROJECT_FOLDER = Path(__file__).resolve().parent.parent


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
    mode: str  # A difficulty name, or MULTIPLAYER
    date: str  # YYYY-MM-DD


def default_path() -> Path:
    """Where stats are kept.

    Running from a clone of the repository, that's stats.json in the project
    folder, which .gitignore keeps out of version control. An installed copy has
    no project folder, so it uses the platform's usual place for app data. The
    SHIRITORI_STATS_FILE environment variable overrides both.
    """
    if override := os.environ.get("SHIRITORI_STATS_FILE"):
        return Path(override)
    if (PROJECT_FOLDER / "pyproject.toml").is_file():
        return PROJECT_FOLDER / "stats.json"
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "shiritori" / "stats.json"


def counts_toward_stats(game: Game) -> bool:
    """Only games played with the standard rules count, so records stay comparable."""
    return game.target_score == DEFAULT_TARGET_SCORE and game.turn_time == DEFAULT_TURN_TIME


@dataclass
class Stats:
    vs_computer: dict[str, Record] = field(default_factory=dict)
    multiplayer_games: int = 0
    high_scores: list[HighScore] = field(default_factory=list)

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
            if data.get("version") != FORMAT_VERSION:
                raise ValueError(f"unsupported version {data.get('version')!r}")
            return cls(
                vs_computer={
                    mode: Record(played=int(record["played"]), won=int(record["won"]))
                    for mode, record in data["vs_computer"].items()
                },
                multiplayer_games=int(data["multiplayer_games"]),
                high_scores=[
                    HighScore(
                        points=int(entry["points"]),
                        word=str(entry["word"]),
                        player=str(entry["player"]),
                        mode=str(entry["mode"]),
                        date=str(entry["date"]),
                    )
                    for entry in data["high_scores"]
                ],
            )
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise StatsError(f"{path} isn't a valid stats file ({error}).") from error

    def save(self, path: Path) -> None:
        data = {
            "version": FORMAT_VERSION,
            "vs_computer": {mode: asdict(record) for mode, record in self.vs_computer.items()},
            "multiplayer_games": self.multiplayer_games,
            "high_scores": [asdict(entry) for entry in self.high_scores],
        }
        # Write to a temporary file first so a crash can't leave a half-written file behind.
        temporary = path.with_name(path.name + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, path)
        except OSError as error:
            raise StatsError(f"Couldn't save {path}: {error}") from error

    def record_game(self, game: Game, today: date) -> list[int]:
        """Add a finished game, and return the high-score ranks (from 1) its words reached."""
        winner = game.winner
        if winner is None:
            raise ValueError("The game isn't over yet.")

        computer = next((p for p in game.players if isinstance(p, ComputerPlayer)), None)
        if computer:
            mode = computer.difficulty.name
            record = self.vs_computer.setdefault(mode, Record())
            record.played += 1
            if winner is not computer:
                record.won += 1
        else:
            mode = MULTIPLAYER
            self.multiplayer_games += 1

        plays = [
            HighScore(move.points, move.word, move.player.name, mode, today.isoformat())
            for move in game.moves
            if not isinstance(move.player, ComputerPlayer)
        ]
        # Sorting is stable, so older entries keep their place ahead of new ties.
        ranked = sorted(self.high_scores + plays, key=lambda entry: entry.points, reverse=True)
        self.high_scores = ranked[:HIGH_SCORE_COUNT]
        return [
            rank
            for rank, entry in enumerate(self.high_scores, 1)
            if any(entry is play for play in plays)
        ]


def format_stats(stats: Stats) -> str:
    lines = ["Record against the computer"]
    rows = []
    for mode in DIFFICULTIES:
        record = stats.vs_computer.get(mode, Record())
        win_rate = f"{record.won / record.played:.0%}" if record.played else "-"
        rows.append([mode, str(record.played), str(record.won), str(record.lost), win_rate])
    lines += _table(["Difficulty", "Played", "Won", "Lost", "Win rate"], rows, align="<>>>>")
    lines += ["", f"Multiplayer games: {stats.multiplayer_games}", "", "High scores"]
    if stats.high_scores:
        rows = [
            [str(rank), str(entry.points), entry.word, entry.player, entry.mode, entry.date]
            for rank, entry in enumerate(stats.high_scores, 1)
        ]
        lines += _table(["#", "Points", "Word", "Player", "Mode", "Date"], rows, align=">><<<<")
    else:
        lines.append("  None yet. Play a game to set one!")
    return "\n".join(lines)


def _table(header: Sequence[str], rows: Sequence[Sequence[str]], align: str) -> list[str]:
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
