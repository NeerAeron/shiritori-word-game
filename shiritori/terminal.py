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

from .style import line_width, paint, width

if sys.platform != "win32":
    import select
    import termios

BANNER = r"""
 _______ __     __        __ __               __
|     __|  |--.|__|.----.|__|  |_.-----.----.|__|
|__     |     ||  ||   _||  |   _|  _  |   _||  |
|_______|__|__||__||__|  |__|____|_____|__|  |__|
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
    """A single-line prompt with a live countdown, such as `  7 | Neer: Kit`.

    Use it as a context manager: the clock starts on entry and a background
    thread redraws the countdown as it ticks. On exit the line is cleared so
    the caller can print the outcome of the turn in its place. The countdown
    keeps going below zero; it is up to the caller what that means.

    *start* is the letter the word must begin with. It is shown from the
    start, in a capital, and counts whether or not the player types it. If
    they do, it turns bold; Backspace can take it back to plain again.

    The countdown shows the seconds left, unless *countdown* is given: it
    turns the seconds taken so far into the text to show instead, such as
    the points a word would score now. *tone*, if given, turns the seconds
    taken so far into the countdown's color, such as "red" once time is up.
    """

    def __init__(
        self,
        label: str,
        seconds: int,
        *,
        start: str = "",
        countdown: Callable[[float], str] | None = None,
        tone: Callable[[float], str | None] | None = None,
        out: TextIO | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.label = label
        self.seconds = seconds
        self.start = start.lower()
        self._countdown = countdown
        self._tone = tone
        self._start_typed = False  # Whether the player has typed the start too
        self._rest = ""  # Everything typed after the start
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

    @property
    def text(self) -> str:
        """The word so far, start included."""
        return self.start + self._rest

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

        The start counts whether or not it's typed: "banana" and "anana" both
        play BANANA, and EEL takes "eel".
        """
        while True:
            key = read_key()
            if key in ENTER_KEYS:
                problem = check(self.text)
                if problem is None:
                    return self.text, self.elapsed()
                self._update(problem)
            elif key in BACKSPACE_KEYS:
                if self._rest:
                    self._rest = self._rest[:-1]
                else:
                    self._start_typed = False
                self._update()
            elif len(key) == 1 and key.isascii() and key.isalpha():
                self._type(key.lower())

    def type_word(
        self,
        word: str,
        delays: Sequence[float],
        sleep: Callable[[float], None] = time.sleep,
    ) -> float:
        """Type out *word* a letter at a time, and return the seconds taken.

        *delays* holds the pause before each letter, then the pause before Enter.
        """
        *before_letters, before_enter = delays
        for letter, delay in zip(word, before_letters, strict=True):
            sleep(delay)
            self._type(letter)
        sleep(before_enter)
        return self.elapsed()

    def _type(self, letter: str) -> None:
        if not self._start_typed and not self._rest and letter == self.start:
            self._start_typed = True
        else:
            self._rest += letter
        self._update()

    def _update(self, message: str = "") -> None:
        with self._lock:
            self._message = message
            self._render()

    def _state(self) -> tuple[str, str | None]:
        """The countdown's text and color, both from one reading of the clock."""
        elapsed = self.elapsed()
        seconds_left = str(math.ceil(self.seconds - elapsed))
        shown = self._countdown(elapsed) if self._countdown else seconds_left
        return shown, self._tone(elapsed) if self._tone else None

    def _tick(self) -> None:
        state = self._state()
        while not self._done.wait(0.05):
            if self._state() != state:
                with self._lock:
                    state = self._state()
                    self._render()

    def _render(self) -> None:
        # Only call this while holding self._lock. Widths are measured without
        # colors, since color codes take up no room on screen.
        shown, tone = self._state()
        field = f"{shown:>3}"
        start = self.start.upper()
        line = (
            f"{paint(field, tone) if tone else field} {paint('|', 'dim')} {self.label}: "
            f"{paint(start, 'bold') if self._start_typed else start}{self._rest}"
        )
        note = self._note(line_width() - width(line))
        # Pad with spaces to erase whatever is left of a longer previous line,
        # then step back so the cursor sits right after the typed text.
        shown_width = width(line) + width(note)
        pad = max(0, self._width - shown_width)
        self._out.write("\r" + line + note + " " * pad + "\b" * (pad + width(note)))
        self._out.flush()
        self._width = shown_width

    def _note(self, room: int) -> str:
        """The problem with the word, cut short at a word or left out to fit in *room* columns."""
        message = self._message
        if len(message) + 4 > room:  # The note adds two spaces and brackets.
            cut = message[: max(0, room - 4) + 1]
            message = cut.rpartition(" ")[0].rstrip() if " " in cut else ""
        return "  " + paint(f"({message})", "red") if message else ""
