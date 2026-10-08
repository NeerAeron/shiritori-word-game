# Shiritori

[![CI](https://github.com/NeerAeron/shiritori-word-game/actions/workflows/ci.yml/badge.svg)](https://github.com/NeerAeron/shiritori-word-game/actions/workflows/ci.yml)

Shiritori (しりとり) is a Japanese word-chain game: each word has to start
where the last one ended. This is an English version that runs in your
terminal. You race a countdown clock against a computer opponent or against
friends on the same keyboard.

```text
First to 100 points wins. Words score a point per letter, plus a point
for every second left on the 10-second clock (or minus one for every
second over).

Neer (T): tiger  +13
    Neer: 13 | Computer: 0
Computer (R): rhubarb  +16
    Neer: 13 | Computer: 16
Neer (B): banana  +14
    Neer: 27 | Computer: 16
  8 | Computer (A): avala
```

## Features

- Play solo against a computer opponent with four difficulty levels, or with
  up to 10 people taking turns at one keyboard.
- A live countdown on every turn. Answer quickly to earn bonus points.
- Instant feedback when a word is rejected, so you can fix it and try again.
- A built-in dictionary of about 112,000 English words.
- Runs on Linux, macOS and Windows, with a single small dependency
  ([readchar](https://pypi.org/project/readchar/)).

## Installation

You need Python 3.10 or newer.

The easiest way to install it is with [pipx](https://pipx.pypa.io/), which
puts the `shiritori` command on your path:

```sh
pipx install git+https://github.com/NeerAeron/shiritori-word-game.git
shiritori
```

To install from a clone instead:

```sh
git clone https://github.com/NeerAeron/shiritori-word-game.git
cd shiritori-word-game
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install .
shiritori                      # or: python -m shiritori
```

## How to play

When the game starts, you choose how many people are playing and enter their
names. If you play alone, you also pick a difficulty for the computer
opponent.

Each turn shows a countdown, the current player, and the letter their word
must start with:

```text
  7 | Neer (K): kit
```

Type a word and press **Enter**. Use **Backspace** to correct mistakes and
**Ctrl+C** to quit at any time.

### Rules

- The first word starts with a random letter. After that, every word starts
  with the last letter of the previous word.
- Words must be in the dictionary, at least 3 letters long, and use only the
  letters A–Z. No hyphens, spaces, or apostrophes.
- A word can only be played once per game.
- If you enter a word that breaks a rule, the game tells you why and you can
  keep editing. The clock keeps running.

### Scoring

A word earns one point per letter plus a time bonus equal to the seconds left
on the clock. Once the clock passes zero it keeps counting down and the bonus
becomes a penalty, so a slow answer can lose you points. The first player to
reach the target score (100 by default) wins.

For example, playing `elephant` (8 letters) with 6 seconds left scores
8 + 6 = 14 points. Playing it 3 seconds after time runs out scores 8 − 3 = 5.

### Computer difficulty

The computer plays real words from the same dictionary. Harder levels play
longer words, which earn more points.

| Difficulty | Word length     |
| ---------- | --------------- |
| easy       | 3–6 letters     |
| medium     | 6–11 letters    |
| hard       | 8 or more       |
| impossible | 13 or more      |

## Options

```text
shiritori [--target-score POINTS] [--turn-time SECONDS]
```

| Option                   | Default | Description                       |
| ------------------------ | ------- | --------------------------------- |
| `--target-score POINTS`  | 100     | Points needed to win              |
| `--turn-time SECONDS`    | 10      | Seconds on the clock each turn    |
| `--version`              |         | Show the version and exit         |
| `-h`, `--help`           |         | Show help and a summary of rules  |

For a quick game, try `shiritori --target-score 50`. For a more relaxed one,
try `shiritori --turn-time 30`.

## Development

Set up an editable install with the development tools:

```sh
pip install -e ".[dev]"
```

Run the tests, linter, and formatter:

```sh
pytest
ruff check .
ruff format .
```

GitHub Actions runs the same checks on Linux, macOS, and Windows for every
push and pull request.

### Project layout

```text
shiritori/
├── cli.py        Command-line options, game setup, and the turn loop
├── game.py       Rules: turn order, word validation, and scoring
├── computer.py   The computer opponent and its difficulty levels
├── terminal.py   The title banner and the live countdown prompt
├── words.py      Loading and indexing the dictionary
└── words.txt     The word list, one lowercase word per line
tests/            The pytest test suite
```

The game logic in `game.py`, `computer.py`, and `words.py` doesn't do any
terminal input or output, so it's easy to test or reuse in a different
interface.
