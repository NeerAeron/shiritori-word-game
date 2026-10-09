# Shiritori

[![CI](https://github.com/NeerAeron/shiritori-word-game/actions/workflows/ci.yml/badge.svg)](https://github.com/NeerAeron/shiritori-word-game/actions/workflows/ci.yml)

Shiritori (しりとり) is a Japanese word-chain game: each word starts where the
last one ended. This English version runs in your terminal. Race the clock
against the computer, or up to 4 friends on one keyboard.

```text
Neer (T): tiger  +13  (5L + 8s)
    Neer: 13 | Computer: 0
Computer (R): rhubarb  +16  (7L + 9s)
    Neer: 13 | Computer: 16
  8 | Neer (B): bana
```

## Features

- **Two modes:** classic, and challenge mode with new challenges and bonuses every turn
- **Five computer levels**, from beginner to impossible
- **Fair turns:** everyone gets the same number of turns
- **Saved stats:** records, high scores, favorite and longest words
- **No dependencies:** just Python 3.10+, on Linux, macOS, or Windows

## Install

Play straight from a folder:

```sh
git clone https://github.com/NeerAeron/shiritori-word-game.git shiritori
cd shiritori
python play.py
```

Or install the `shiritori` command:

```sh
pipx install git+https://github.com/NeerAeron/shiritori-word-game.git
shiritori
```

## How to play

- Name a word that starts with the last letter of the previous word.
- Words must be real, 3+ letters, A–Z only, and not already played this game.
- **Score:** a point per letter, plus a point per second left on the 10-second
  clock, shown as `(5L + 8s)`. Run out of time and you lose a point per second over.
- **Win:** reach 100 points (150 in challenge mode). The round is played out
  so everyone gets the same number of turns, then the highest score wins.

Type a word and press **Enter**. **Backspace** fixes mistakes, **Ctrl+C**
quits. Run `python play.py --rules` for a refresher in the terminal.

## Challenge mode

Every word must also meet a challenge that changes each turn, such as *end
with S*, *no letter E*, or *hide an animal (ANT, BAT, CAT…)*. There are 119,
each leaving at least 100 words to choose from, and harder computer levels
get harder ones. Vowels are A, E, I, O, U.

Two bonuses add to your score:

- **Round bonus:** a new one each turn, such as *+2 per S* or *+4 per double
  letter*. Every letter or pair counts, so *assess* earns +8 from *+2 per S*.
  It shows up as `B` in the score.
- **Game bonus:** one per game, such as *include Q* or *U is the only vowel*.
  Words that meet it score 1.5x–3x, and the harder the bonus, the more it pays.

```text
  Challenge: include Y | +2 per S | x2.3: U is the only vowel
Neer (D): dusty  +37  (5L + 2B + 9s) x2.3
```

Time points (the `s` in the score) start at +10 and drop 1 every 2 seconds.
At 0 there are 4 seconds of grace before they go negative. Challenge mode
plays to 150.

## Computer levels

| Level      | Word length | Plays tactically |
| ---------- | ----------- | ---------------- |
| beginner   | 3–6         | no               |
| easy       | 5–9         | no               |
| medium     | 7–11        | a little         |
| hard       | 9–15        | more             |
| impossible | 10–16       | the most         |

Like a person, the computer is quicker with common letters like S and slower
with awkward ones like Y. Tactical levels try to leave you an awkward letter,
and harder levels go for bonuses more often.

## Stats

```sh
python play.py --stats        # records, high scores, and word stats
python play.py --reset-stats  # start over
```

Stats are saved in `stats.json` inside the game's folder (gitignored). Games
with a custom `--target-score` or `--turn-time` don't count.

## Options

| Option                  | What it does                                    |
| ----------------------- | ----------------------------------------------- |
| `--target-score POINTS` | Points to win (default 100, or 150 in challenge) |
| `--turn-time SECONDS`   | Seconds per turn (default 10, or 20 in challenge) |
| `--rules`               | Explain how to play                             |
| `--stats`               | Show your stats                                 |
| `--reset-stats`         | Erase your stats                                |

If you installed it, use `shiritori` in place of `python play.py`.

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
| `shiritori/terminal.py`   | Keyboard input and the countdown prompt   |
| `shiritori/words.py`      | The dictionary (`words.txt`)              |

## License

[MIT](LICENSE)
