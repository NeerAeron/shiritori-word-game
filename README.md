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

- **Two modes:** classic Shiritori, and challenge mode, where every word must
  also meet a spelling challenge and a bonus challenge multiplies your points.
- **Solo or together:** play the computer at four difficulty levels, or with
  up to 10 people taking turns at one keyboard.
- **A live countdown** on every turn. Answer quickly to earn bonus points.
- **Instant feedback** when a word is rejected, so you can fix it and try again.
- **Saved stats:** your record against each difficulty, high scores, favorite
  word, longest word, and more.
- **Nothing to install.** The whole game, including your stats, lives in one
  folder. It needs only Python and runs on Linux, macOS, and Windows.

## Getting started

You need Python 3.10 or newer. Download the game with git:

```sh
git clone https://github.com/NeerAeron/shiritori-word-game.git shiritori
```

Or download the ZIP from GitHub (**Code → Download ZIP**) and unzip it. Then
start the game from the folder:

```sh
cd shiritori
python play.py
```

On some systems the command is `python3` instead of `python`.

Everything the game uses or saves stays inside its folder. To remove it, just
delete the folder.

## How to play

When the game starts, you choose a mode and how many people are playing, and
enter their names. If you play alone, you also pick a difficulty for the
computer opponent.

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

## Challenge mode

In challenge mode, every word must also meet a **challenge** that changes
each turn. There are 100 of them, from easy to hard, such as:

- end with S
- no letter E
- include a double letter
- second letter is R
- hide an animal (ANT, BAT, CAT, COW, DOG, HEN, OWL, PIG, RAT)
- alternate consonants and vowels

The game only sets a challenge when there are plenty of words that meet it,
so none is ever too hard. Challenges never depend on how long a word is.
Vowels are A, E, I, O, and U; Y counts as a consonant.

Each game also has one **bonus challenge** that lasts the whole game, like
"use all five vowels" or "no A, E, or I". A word that meets the turn's
challenge *and* the bonus challenge has its points multiplied:

```text
  Challenge: include Y   [x2.3 bonus: U is the only vowel]
Neer (D): dusty  +51  (x2.3 bonus!)
    Neer: 51 | Computer: 0
  Challenge: no letter N   [x2.3 bonus: U is the only vowel]
Computer (Y): yogurt  +19
    Neer: 51 | Computer: 19
```

Harder bonus challenges pay more, from about 1.5x to 4x, with a little
randomness so no two games are quite the same. Multipliers around 2x are the
most common, smaller ones are slightly rarer, and big ones are much rarer.
A bonus multiplies points but never makes a late answer's penalty worse.

The clock is 20 seconds in challenge mode, to give you time to think.

## Computer difficulty

The computer plays real words from the same dictionary. Harder levels play
longer words, which earn more points. In challenge mode, harder levels also
think faster and go for the bonus challenge more often.

| Difficulty | Word length | Goes for the bonus (challenge mode) |
| ---------- | ----------- | ----------------------------------- |
| easy       | 3–6 letters | 10% of turns                        |
| medium     | 6–11        | 25%                                 |
| hard       | 8 or more   | 40%                                 |
| impossible | 13 or more  | 60%                                 |

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
python play.py --stats
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

Stats are saved in `stats.json` in the game folder, never anywhere else on
your computer, and never uploaded. The file is listed in `.gitignore`, so it
never gets committed. To start over, run `python play.py --reset-stats`.

Only games played with the standard rules count, so records stay comparable.
Games with a custom `--target-score` or `--turn-time` aren't recorded, and
neither are games you quit with Ctrl+C.

## Options

```text
python play.py [--target-score POINTS] [--turn-time SECONDS] [--stats | --reset-stats]
```

| Option                  | Default                     | Description                      |
| ----------------------- | --------------------------- | -------------------------------- |
| `--target-score POINTS` | 100                         | Points needed to win             |
| `--turn-time SECONDS`   | 10, or 20 in challenge mode | Seconds on the clock each turn   |
| `--stats`               |                             | Show your records and stats      |
| `--reset-stats`         |                             | Erase your stats (asks first)    |
| `--version`             |                             | Show the version and exit        |
| `-h`, `--help`          |                             | Show help and a summary of rules |

For a quick game, try `python play.py --target-score 50`. For a more relaxed
one, try `python play.py --turn-time 30`. Neither counts toward your stats.

## Development

The tests use [pytest](https://pytest.org/) and the code is linted and
formatted with [Ruff](https://docs.astral.sh/ruff/). To keep them inside the
game folder too, install them in a virtual environment there:

```sh
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install pytest ruff
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
