"""Colors and symbols for the terminal, with plain-text fallbacks.

Colors are only used when standard output is a terminal, the NO_COLOR
environment variable is unset (see https://no-color.org) and TERM isn't
"dumb". On Windows the console must also accept ANSI escape codes, which
Windows 10 and later do once asked to.
"""

from __future__ import annotations

import os
import re
import sys
from typing import TextIO

_CODES = {
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
}
_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

_colors = False


def use_colors(enabled: bool) -> None:
    """Turn colors on or off for everything painted from now on."""
    global _colors
    _colors = enabled


def colors_supported(stream: TextIO) -> bool:
    """Whether *stream* is a terminal that should get colors."""
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    if not stream.isatty():
        return False
    return sys.platform != "win32" or _enable_windows_escape_codes()


def _enable_windows_escape_codes() -> bool:
    """Ask the Windows console to understand ANSI escape codes."""
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # Standard output
        mode = wintypes.DWORD()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        virtual_terminal_processing = 0x0004
        return bool(kernel32.SetConsoleMode(handle, mode.value | virtual_terminal_processing))
    except (AttributeError, OSError):
        return False


def paint(text: str, *styles: str) -> str:
    """*text* in the given styles, such as "bold" and "green", if colors are on."""
    if not _colors or not styles or not text:
        return text
    codes = ";".join(_CODES[style] for style in styles)
    return f"\x1b[{codes}m{text}\x1b[0m"


def width(text: str) -> int:
    """How many columns *text* takes up on screen, ignoring color codes."""
    return len(_ESCAPE.sub("", text))


def symbol(fancy: str, plain: str, stream: TextIO | None = None) -> str:
    """*fancy* if *stream* (standard output) can encode it, else *plain*."""
    encoding = getattr(stream or sys.stdout, "encoding", None) or "ascii"
    try:
        fancy.encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return plain
    return fancy
