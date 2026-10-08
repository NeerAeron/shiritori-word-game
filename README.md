# Shiritori

[![CI](https://github.com/NeerAeron/shiritori-word-game/actions/workflows/ci.yml/badge.svg)](https://github.com/NeerAeron/shiritori-word-game/actions/workflows/ci.yml)

Shiritori (しりとり) is a Japanese word-chain game: each word has to start
where the last one ended. This is an English version that runs in your
terminal. You race a countdown clock against a computer opponent or against
friends on the same keyboard.

```text
Neer (T): tiger  +13
    Neer: 13 | Computer: 0
Computer (R): rhubarb  +16
    Neer: 13 | Computer: 16
Neer (B): banana  +14
    Neer: 27 | Computer: 16
  8 | Computer (A): avala
```

## Features

- **Two modes:** classic Shiritori, and challenge mode, where every word must
  also meet a spelling challenge and a bonus challenge multiplies your points.
- **Solo or together:** play the computer at four difficulty levels, or with
  up to 4 people taking turns at one keyboard.
- **Fair turns:** everyone always gets the same number of turns, so going
  first is no advantage.
- **A live countdown** on every turn. Answer quickly to earn bonus points.
- **Instant feedback** when a word is rejected, so you can fix it and try again.
- **Saved stats:** your record against each difficulty, high scores, favorite
  word, longest word, and more.
- **Self-contained.** No dependencies beyond Python, and the game, including
  your stats, stays in its own folder. Runs on Linux, macOS, and Windows.

## Getting started

You need Python 3.10 or newer. There are two ways to get the game.

### Play from a folder (no install)

Download the game with git, or download the ZIP from GitHub
(**Code → Download ZIP**) and unzip it:

```sh
git clone https://github.com/NeerAeron/shiritori-word-game.git shiritori
cd shiritori
python play.py
```

On some systems the command is `python3` instead of `python`. Everything the
game uses or saves stays inside this folder. To remove it, delete the folder.

### Install the `shiritori` command

With [pipx](https://pipx.pypa.io/), which keeps the game in its own isolated
environment:

```sh
pipx install git+https://github.com/NeerAeron/shiritori-word-game.git
shiritori
```

Or with pip (ideally inside a virtual environment):

```sh
pip install git+https://github.com/NeerAeron/shiritori-word-game.git
shiritori
```

`pipx uninstall shiritori-word-game` or `pip uninstall shiritori-word-game`
removes it again.

## How to play

When the game starts, you choose a mode and how many people are playing (up
to 4), and enter their names. If you play alone, you also pick a difficulty
for the computer opponent.

Each turn shows a countdown, the current player, and the letter their word
must start with:

```text
  7 | Neer (K): kit
```

Type a word and press **Enter**. Use **Backspace** to correct mistakes and
**Ctrl+C** to quit at any time.

The game doesn't repeat the instructions every time. To read them in the
terminal, run `python play.py --rules` (or `shiritori --rules`).

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
becomes a penalty, so a slow answer can lose you points.

For example, playing `elephant` (8 letters) with 6 seconds left scores
8 + 6 = 14 points. Playing it 3 seconds after time runs out scores 8 − 3 = 5.

### Winning

The game ends when someone reaches the target score: 100 points, or 150 in
challenge mode. The rest of that round is still played, so everyone gets the
same number of turns, and then the highest score wins. A tie for the lead
plays one more round.

Without that last round, whoever goes first wins about two games in three
between evenly matched players. With it, it's an even split.

## Challenge mode

In challenge mode, every word must also meet a **challenge** that changes
each turn. There are 131 of them, from easy to hard, such as:

- end with S
- no letter E
- include a double letter
- second letter is R
- hide an animal (ANT, BAT, CAT, COW, DOG, HEN, OWL, PIG, RAT)
- alternate consonants and vowels

The game only sets a challenge when there are plenty of words that meet it,
so none is ever too hard. Challenges never depend on how long a word is.
Vowels are A, E, I, O, and U; Y counts as a consonant.

The challenges are ranked from easiest to hardest, and each difficulty draws
from a bell curve along that ranking. Easier difficulties lean toward the
easy end; impossible is centered. Games between people use the hard mix.

| Difficulty | Bell curve           | Easy | Medium | Hard |
| ---------- | -------------------- | ---: | -----: | ---: |
| easy       | heavily toward easy  |  73% |    26% |   1% |
| medium     | toward easy          |  49% |    46% |   4% |
| hard       | slightly toward easy |  31% |    58% |  10% |
| impossible | centered             |  24% |    58% |  18% |

Each game also has one **bonus challenge** that lasts the whole game, like
"use all five vowels" or "no A, E, or I". It's picked at random from 30
bonus challenges, each equally likely. A word that meets the turn's
challenge *and* the bonus challenge has its points multiplied:

```text
  Challenge: include Y   (bonus x2.3: U is the only vowel)
Neer (D): dusty  +51  (x2.3 bonus)
    Neer: 51 | Computer: 0
  Challenge: no letter N   (bonus x2.3: U is the only vowel)
Computer (Y): yogurt  +19
    Neer: 51 | Computer: 19
```

Harder bonus challenges pay more, from 1.5x up to at most 3x, with a little
randomness so no two games are quite the same. Multipliers around 2x are the
most common, smaller ones are slightly rarer, and 3x ones are the rarest.
A bonus multiplies points but never makes a late answer's penalty worse.

Challenge mode has a 20-second clock and plays to 150 points. Before the
first turn, the game shows the bonus challenge and counts down from 5.

## Computer difficulty

The computer plays real words from the same dictionary, and takes time to
think and type like a person does. Harder levels play longer words, think and
type faster, and in challenge mode go for the bonus challenge more often.

The levels are tuned against a simulated typical player, who takes about 4
seconds to think of a word in classic mode and 8 in challenge mode:

| Difficulty | Word length | Typical player wins (classic / challenge) |
| ---------- | ----------- | ----------------------------------------- |
| easy       | 3–6 letters | about 84% / 85%                           |
| medium     | 4–8         | about 60% / 61%                           |
| hard       | 5–10        | about 24% / 23%                           |
| impossible | 7–12        | about 3% / 1%                             |

## Stats

After each game, Shiritori saves:

- **Your record against the computer:** games played, won, and lost at each
  difficulty, separately for classic and challenge mode.
- **High scores:** the 10 highest-scoring words in each mode, with who played
  them, the opponent, and the date. The computer's words don't count.
- **Your words:** how many you've played, your favorite (most played) word,
  your longest word, and the letters your words most often start and end with.

The game tells you when you set a new high score or a new longest word, and
shows your updated record. To see everything, run:

```sh
python play.py --stats      # or, if you installed it: shiritori --stats
```

```text
Your words
  Words played              212
  Favorite word             yogurt (played 4 times)
  Longest word              electromagnetic (15 letters)
  Most common first letter  S (31 words)
  Most common last letter   E (40 words)

Classic mode against the computer
  Difficulty  Played  Won  Lost  Win rate
  easy             4    3     1       75%
  medium           2    1     1       50%
  hard             1    0     1        0%
  impossible       0    0     0         -
```

Stats are saved in a `stats.json` file inside the game's own folder, never
anywhere else on your computer, and never uploaded:

- **Playing from a folder:** next to `play.py`. The file is listed in
  `.gitignore`, so it never gets committed.
- **Installed with pip or pipx:** in the installed package's own folder
  (for pipx, that's inside the game's isolated environment).

`--stats` shows the exact path. To start over, run `--reset-stats`.

Only games played with the standard rules count, so records stay comparable.
Games with a custom `--target-score` or `--turn-time` aren't recorded, and
neither are games you quit with Ctrl+C.

## Options

```text
python play.py [--target-score POINTS] [--turn-time SECONDS] [--rules | --stats | --reset-stats]
```

If you installed the game, use `shiritori` in place of `python play.py`.

| Option                  | Default                       | Description                    |
| ----------------------- | ----------------------------- | ------------------------------ |
| `--target-score POINTS` | 100, or 150 in challenge mode | Points needed to win           |
| `--turn-time SECONDS`   | 10, or 20 in challenge mode   | Seconds on the clock each turn |
| `--rules`               |                               | Explain how to play            |
| `--stats`               |                               | Show your records and stats    |
| `--reset-stats`         |                               | Erase your stats (asks first)  |
| `--version`             |                               | Show the version and exit      |
| `-h`, `--help`          |                               | Show the options               |

For a quick game, try `python play.py --target-score 50`. For a more relaxed
one, try `python play.py --turn-time 30`. Neither counts toward your stats.

## Development

The tests use [pytest](https://pytest.org/) and the code is linted and
formatted with [Ruff](https://docs.astral.sh/ruff/). Set up a virtual
environment in the game folder with an editable install and both tools:

```sh
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Then run the tests, linter, and formatter:

```sh
pytest
ruff check .
ruff format .
```

GitHub Actions runs the same checks on Linux, macOS, and Windows for every
push and pull request.

### Project layout

```text
play.py           Starts the game
shiritori/
├── cli.py        Command-line options, game setup, and the turn loop
├── game.py       Rules for classic mode: turns, word checks, and scoring
├── challenges.py Challenge mode: the challenges, bonuses, and multipliers
├── computer.py   The computer opponent and its difficulty levels
├── stats.py      Saved records, high scores, and word stats
├── terminal.py   Keyboard input, the title banner, and the countdown prompt
├── words.py      Loading and indexing the dictionary
└── words.txt     The word list, one lowercase word per line
tests/            The pytest test suite
```

The game logic in `game.py`, `challenges.py`, `computer.py`, and `words.py`
doesn't do any terminal input or output, so it's easy to test or reuse in a
different interface. The tests never touch your real stats; each test uses a
temporary folder.

## License

Shiritori is released under the [MIT License](LICENSE).
