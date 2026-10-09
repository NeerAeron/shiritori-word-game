"""Terminal output and keyboard input."""

from __future__ import annotations

import math
import os
import sys
import threading
import time
from collections.abc import Callable, Sequence
from types import ModuleType
from typing import TextIO

if sys.platform != "win32":
    import select
    import termios

BANNER = r"""
 _______ __     __        __ __               __
|     __|  |--.|__|.----.|__|  |_.-----.----.|__|
|__     |     ||  ||   _||  |   _|  _  |   _||  |
|_______|__|__||__||__|  |__|____|_____|__|  |__|

  The word-chain game, by Neer
"""

# Enter arrives as "\n" or "\r", and Backspace as "\x7f" or "\x08", depending on
# the platform and terminal; accept them all.
ENTER_KEYS = frozenset({"\r", "\n"})
BACKSPACE_KEYS = frozenset({"\x7f", "\x08"})


class PosixKeyboard:
    """Reads keypresses one at a time on Linux and macOS.

    Inside a ``with`` block the terminal stops echoing keys and stops waiting
    for Enter, so each key can be handled the moment it's pressed. Ctrl+C still
    raises KeyboardInterrupt.
    """

    def __init__(self, fd: int | None = None) -> None:
        self._fd = sys.stdin.fileno() if fd is None else fd
        self._saved: list | None = None

    def __enter__(self) -> PosixKeyboard:
        self._saved = termios.tcgetattr(self._fd)
        mode = termios.tcgetattr(self._fd)
        mode[3] &= ~(termios.ICANON | termios.ECHO)
        mode[6][termios.VMIN] = 1
        mode[6][termios.VTIME] = 0
        termios.tcsetattr(self._fd, termios.TCSAFLUSH, mode)
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._saved is not None:
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)

    def discard_pending(self) -> None:
        """Throw away keys pressed before now, such as during the computer's turn."""
        termios.tcflush(self._fd, termios.TCIFLUSH)

    def read_key(self) -> str:
        """Wait for a keypress and return it.

        Arrow and function keys send an escape sequence, which is returned whole
        so that the letters in it aren't mistaken for typing.
        """
        key = self._read_char()
        if key == "\x1b" and select.select([self._fd], [], [], 0.05)[0]:
            key += self._read_char()
            if key[-1] in "[O":
                while True:
                    key += self._read_char()
                    if "@" <= key[-1] <= "~" and key != "\x1b[[":
                        break
        return key

    def _read_char(self) -> str:
        byte = os.read(self._fd, 1)
        if not byte:
            raise EOFError
        return byte.decode("latin-1")


class WindowsKeyboard:
    """Reads keypresses one at a time on Windows, where keys are never echoed."""

    def __init__(self, console: ModuleType | None = None) -> None:
        if console is None:
            import msvcrt as console
        self._console = console

    def __enter__(self) -> WindowsKeyboard:
        return self

    def __exit__(self, *exc_info: object) -> None:
        pass

    def discard_pending(self) -> None:
        """Throw away keys pressed before now, such as during the computer's turn."""
        while self._console.kbhit():
            self._console.getwch()

    def read_key(self) -> str:
        """Wait for a keypress and return it."""
        key = self._console.getwch()
        if key == "\x03":
            raise KeyboardInterrupt
        if key in ("\x00", "\xe0"):
            key += self._console.getwch()  # Arrow and function keys send a second code.
        return key


Keyboard = WindowsKeyboard if sys.platform == "win32" else PosixKeyboard


class TurnPrompt:
    """A single-line prompt with a live countdown, such as `  7 | Neer (K): kit`.

    Use it as a context manager: the clock starts on entry and a background
    thread redraws the countdown as it ticks. On exit the line is cleared so
    the caller can print the outcome of the turn in its place. The countdown
    keeps going below zero; it is up to the caller what that means.

    The countdown shows the seconds left, unless *countdown* is given: it
    turns the seconds taken so far into the text to show instead, such as
    the points a word would score now.
    """

    def __init__(
        self,
        label: str,
        seconds: int,
        *,
        countdown: Callable[[float], str] | None = None,
        out: TextIO | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.label = label
        self.seconds = seconds
        self._countdown = countdown
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
        self, check: Callable[[str], str | None], read_key: Callable[[], str]
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

    def _shown(self) -> str:
        if self._countdown:
            return self._countdown(self.elapsed())
        return str(self.remaining())

    def _tick(self) -> None:
        shown = self._shown()
        while not self._done.wait(0.05):
            if self._shown() != shown:
                with self._lock:
                    shown = self._shown()
                    self._render()

    def _render(self) -> None:
        # Only call this while holding self._lock.
        line = f"{self._shown():>3} | {self.label}: {self.text}"
        note = f"  ({self._message})" if self._message else ""
        # Pad with spaces to erase whatever is left of a longer previous line,
        # then step back so the cursor sits right after the typed text.
        pad = max(0, self._width - len(line + note))
        self._out.write("\r" + line + note + " " * pad + "\b" * (pad + len(note)))
        self._out.flush()
        self._width = len(line + note)
