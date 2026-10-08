"""Terminal output and keyboard input."""

from __future__ import annotations

import math
import sys
import threading
import time
from collections.abc import Callable, Sequence
from typing import TextIO

import readchar

BANNER = r"""
 _______ __     __        __ __               __
|     __|  |--.|__|.----.|__|  |_.-----.----.|__|
|__     |     ||  ||   _||  |   _|  _  |   _||  |
|_______|__|__||__||__|  |__|____|_____|__|  |__|

  The word-chain game, by Neer
"""

# readchar reports Enter as "\n" on POSIX and "\r" on Windows, and Backspace as
# "\x7f" or "\x08" depending on the platform and terminal; accept them all.
ENTER_KEYS = frozenset({"\r", "\n", readchar.key.ENTER})
BACKSPACE_KEYS = frozenset({"\x7f", "\x08", readchar.key.BACKSPACE})


class TurnPrompt:
    """A single-line prompt with a live countdown, such as `  7 | Neer (K): kit`.

    Use it as a context manager: the clock starts on entry and a background
    thread redraws the countdown as it ticks. On exit the line is cleared so
    the caller can print the outcome of the turn in its place. The countdown
    keeps going below zero; it is up to the caller what that means.
    """

    def __init__(
        self,
        label: str,
        seconds: int,
        *,
        out: TextIO | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.label = label
        self.seconds = seconds
        self.text = ""
        self._message = ""
        self._out = out or sys.stdout
        self._clock = clock
        self._start = clock()
        self._width = 0
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._ticker = threading.Thread(target=self._tick, daemon=True)

    def __enter__(self) -> TurnPrompt:
        self._start = self._clock()
        with self._lock:
            self._render()
        self._ticker.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._done.set()
        self._ticker.join()
        self._out.write("\r" + " " * self._width + "\r")
        self._out.flush()

    def elapsed(self) -> float:
        """Seconds since the turn started."""
        return self._clock() - self._start

    def remaining(self) -> int:
        """Whole seconds left on the clock; zero or negative once time is up."""
        return math.ceil(self.seconds - self.elapsed())

    def read_word(
        self,
        check: Callable[[str], str | None],
        read_key: Callable[[], str] = readchar.readkey,
    ) -> tuple[str, float]:
        """Let the player type a word, and return it with the seconds taken.

        Only the letters a-z are accepted. Pressing Enter submits the word if
        *check* returns None for it; otherwise the problem *check* describes is
        shown next to the word and the player can carry on editing.
        """
        while True:
            key = read_key()
            if key in ENTER_KEYS:
                problem = check(self.text)
                if problem is None:
                    return self.text, self.elapsed()
                self._update(self.text, problem)
            elif key in BACKSPACE_KEYS:
                self._update(self.text[:-1])
            elif len(key) == 1 and key.isascii() and key.isalpha():
                self._update(self.text + key.lower())

    def type_word(
        self,
        word: str,
        delays: Sequence[float],
        sleep: Callable[[float], None] = time.sleep,
    ) -> float:
        """Type *word* out a letter at a time, and return the seconds taken.

        *delays* holds the pause before each letter, then the pause before Enter.
        """
        *before_letters, before_enter = delays
        for letter, delay in zip(word, before_letters, strict=True):
            sleep(delay)
            self._update(self.text + letter)
        sleep(before_enter)
        return self.elapsed()

    def _update(self, text: str, message: str = "") -> None:
        with self._lock:
            self.text = text
            self._message = message
            self._render()

    def _tick(self) -> None:
        shown = self.remaining()
        while not self._done.wait(0.05):
            if self.remaining() != shown:
                with self._lock:
                    shown = self.remaining()
                    self._render()

    def _render(self) -> None:
        # Only call this while holding self._lock.
        line = f"{self.remaining():>3} | {self.label}: {self.text}"
        note = f"  ({self._message})" if self._message else ""
        # Pad with spaces to erase whatever is left of a longer previous line,
        # then step back so the cursor sits right after the typed text.
        pad = max(0, self._width - len(line + note))
        self._out.write("\r" + line + note + " " * pad + "\b" * (pad + len(note)))
        self._out.flush()
        self._width = len(line + note)
