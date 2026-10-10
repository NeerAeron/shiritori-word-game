# Shiritori

[![CI](https://github.com/NeerAeron/shiritori-word-game/actions/workflows/ci.yml/badge.svg)](https://github.com/NeerAeron/shiritori-word-game/actions/workflows/ci.yml)

Shiritori (しりとり) is a Japanese word-chain game: each word starts where the
last one ended. This English version runs in your terminal. Race the clock
against the computer, or up to 4 friends on one keyboard.

```text
+13 | Neer: Tiger  (5L + 8s)
      Neer 13 · Computer 0

+16 | Computer: Rhubarb  (7L + 9s)
      Neer 13 · Computer 16

  8 | Neer: Bana
```

## Features

- **Two modes:** classic, and challenge mode with new requirements and bonuses every turn
- **Five computer levels**, from beginner to impossible
- **Fair turns** and **saved stats** (records, high scores, best games, favorite words)
- **A few colors** where your terminal supports them (`NO_COLOR` turns them off)
- **No dependencies:** Python 3.10+ on Linux, macOS, or Windows

## Install

```sh
git clone https://github.com/NeerAeron/shiritori-word-game.git shiritori
cd shiritori
python play.py
```

Or install the `shiritori` command with
`pipx install git+https://github.com/NeerAeron/shiritori-word-game.git`.

## How to play

- Name a real word (3+ letters, not yet played) that starts with the last
  letter of the previous word. That letter is filled in, so typing it is
  optional; it turns bold if you do.
- **Score:** a point per letter plus a point per second left on the 10-second
  clock, shown as `(5L + 8s)`. Run out of time and you lose a point a second.
- **Win:** reach 100 points (150 in challenge mode). The round is played out
  so everyone gets the same number of turns.

**Enter** submits, **Backspace** fixes mistakes, **Ctrl+C** quits, and
`python play.py --rules` explains it all in the terminal.

## Challenge mode

Every word must also meet a requirement (REQ) that changes each turn, such as
*end with S* or *hide an animal (ANT, BAT, CAT…)*. Harder computer levels get
harder ones. Vowels are A, E, I, O, U.

- **Round bonus:** new each turn and stacking, such as *+2 per S* (*assess*
  earns +8). Letter bonuses are sometimes worth 1 or 2 more. Shown as `B`.
- **Game bonus:** one per game, such as *include Q*. Words that meet it score
  1.5x–4x, more for harder bonuses.
- **Time points** (`s`) start at +10 and drop 1 every 2 seconds, with 4
  seconds of grace at 0 before they go negative.

```text
REQ: include Y | +2 per S, x2.3: U is the only vowel
+37 | Neer: Dusty  (5L + 2B + 9s) x2.3
```

## Computer levels

| Level      | Word length (classic) | Plays tactically |
| ---------- | --------------------- | ---------------- |
| beginner   | 3–6                   | no               |
| easy       | 5–9                   | no               |
| medium     | 7–12                  | a little         |
| hard       | 9–16                  | more             |
| impossible | 10–16                 | the most         |

Like a person, the computer is quicker with easy letters like S. Harder levels
try to leave you awkward letters and go for bonuses more often. In challenge
mode every level plays shorter words and thinks longer, like a person meeting
each requirement.

## Options

| Option                  | What it does                                      |
| ----------------------- | ------------------------------------------------- |
| `--target-score POINTS` | Points to win (default 100, or 150 in challenge)  |
| `--turn-time SECONDS`   | Seconds per turn (default 10, or 20 in challenge) |
| `--rules`               | Explain how to play                               |
| `--stats`               | Show your records, high scores, and best games    |
| `--reset-stats`         | Erase your stats                                  |

Stats live in `stats.json` in the game's folder. Games with a custom target or
turn time don't count. If you installed the command, use `shiritori` in place
of `python play.py`.

## Development

```sh
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest && ruff check . && ruff format --check .
```

| File                      | What it does                              |
| ------------------------- | ----------------------------------------- |
| `play.py`                 | Starts the game                           |
| `shiritori/cli.py`        | Options, setup, and the turn loop         |
| `shiritori/game.py`       | Rules: turns, word checks, scoring        |
| `shiritori/challenges.py` | Challenge mode and bonuses                |
| `shiritori/computer.py`   | The computer opponent                     |
| `shiritori/stats.py`      | Saved stats                               |
| `shiritori/style.py`      | Colors and symbols, with plain fallbacks  |
| `shiritori/terminal.py`   | Keyboard input and the countdown prompt   |
| `shiritori/words.py`      | The dictionary (`words.txt`)              |

## License

[MIT](LICENSE)
