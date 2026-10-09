"""Colors and symbols for the terminal, with plain-text fallbacks.

Colors are only used when standard output is a terminal, the NO_COLOR
environment variable is unset (see https://no-color.org) and TERM isn't
"dumb". On Windows the console must also accept ANSI escape codes, which
Windows 10 and later do once asked to.
"""

from __future__ import annotations

import atexit
import os
import re
import shutil
import sys
from typing import TextIO

_CODES = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33", "magenta": "35"}
_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
# Some of the symbols are a different width in Chinese, Japanese and Korean terminals.
_WIDE_LOCALES = ("ja", "ko", "zh")

_colors = False
_symbols = True


def use_colors(enabled: bool) -> None:
    """Turn colors on or off for everything painted from now on."""
    global _colors
    _colors = enabled


def use_symbols(enabled: bool) -> None:
    """Choose between the non-ASCII symbols and their plain fallbacks."""
    global _symbols
    _symbols = enabled


def colors_supported(stream: TextIO) -> bool:
    """Whether *stream* is a terminal that should get colors."""
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    if not stream.isatty():
        return False
    return sys.platform != "win32" or _enable_windows_escape_codes()


def symbols_supported(stream: TextIO) -> bool:
    """Whether *stream* can show the symbols, each one column wide."""
    try:
        "»·".encode(stream.encoding or "ascii")
    except (UnicodeEncodeError, LookupError):
        return False
    for name in ("LC_ALL", "LC_CTYPE", "LANG"):
        if value := os.environ.get(name):
            return not value.lower().startswith(_WIDE_LOCALES)
    return True


def _enable_windows_escape_codes() -> bool:
    """Ask the Windows console to understand ANSI escape codes on stdout and stderr.

    Returns whether it worked for stdout. The consoles get their old settings
    back when the game exits.
    """
    try:
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False
    # Handles are pointer-sized, so say so: ctypes would otherwise assume an int.
    kernel32.GetStdHandle.restype = ctypes.c_void_p
    kernel32.GetConsoleMode.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
    kernel32.SetConsoleMode.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    virtual_terminal_processing = 0x0004
    worked = {}
    for handle_id in (-11, -12):  # Standard output, standard error
        handle = kernel32.GetStdHandle(handle_id)
        mode = ctypes.c_ulong()
        worked[handle_id] = bool(
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            and kernel32.SetConsoleMode(handle, mode.value | virtual_terminal_processing)
        )
        if worked[handle_id]:
            atexit.register(kernel32.SetConsoleMode, handle, mode.value)
    return worked[-11]


def paint(text: str, *styles: str) -> str:
    """*text* in the given styles, such as "bold" or "green", if colors are on."""
    if not _colors or not styles or not text:
        return text
    codes = ";".join(_CODES[style] for style in styles)
    return f"\x1b[{codes}m{text}\x1b[0m"


def plain(text: str) -> str:
    """*text* without any colors."""
    return _ESCAPE.sub("", text)


def width(text: str) -> int:
    """How many columns *text* takes up on screen, ignoring colors."""
    return len(plain(text))


def symbol(fancy: str, fallback: str) -> str:
    """*fancy*, or *fallback* if symbols are off."""
    return fancy if _symbols else fallback


def line_width() -> int:
    """How wide a line can be without wrapping, leaving the last column free."""
    return min(79, shutil.get_terminal_size((80, 24)).columns - 1)
