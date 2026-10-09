import ctypes
import io

import pytest

from shiritori import style


class FakeStream(io.StringIO):
    def __init__(self, tty=True, encoding="utf-8"):
        super().__init__()
        self._tty = tty
        self._encoding = encoding

    def isatty(self):
        return self._tty

    @property
    def encoding(self):
        return self._encoding


def test_paint_is_plain_text_when_colors_are_off():
    assert style.paint("hello", "bold", "green") == "hello"


def test_paint_wraps_text_in_color_codes_when_colors_are_on():
    style.use_colors(True)
    assert style.paint("hello", "bold") == "\x1b[1mhello\x1b[0m"
    assert style.paint("hello", "red") == "\x1b[31mhello\x1b[0m"
    assert style.paint("", "red") == ""
    assert style.paint("hello") == "hello"


def test_width_and_plain_ignore_color_codes():
    style.use_colors(True)
    text = style.paint("+10", "yellow") + " | " + style.paint("B", "bold")
    assert style.plain(text) == "+10 | B"
    assert style.width(text) == 7


@pytest.mark.parametrize(
    ("env", "tty", "supported"),
    [
        ({}, True, True),
        ({}, False, False),
        ({"NO_COLOR": "1"}, True, False),
        ({"TERM": "dumb"}, True, False),
        ({"NO_COLOR": ""}, True, True),  # only a non-empty NO_COLOR counts
    ],
)
def test_colors_only_go_to_terminals_that_want_them(monkeypatch, env, tty, supported):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setattr(style.sys, "platform", "linux")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert style.colors_supported(FakeStream(tty=tty)) is supported


@pytest.mark.parametrize(
    ("encoding", "lang", "supported"),
    [
        ("utf-8", "en_US.UTF-8", True),
        ("ascii", "en_US.UTF-8", False),
        ("cp1252", "", True),
        ("cp437", "", True),
        ("cp932", "", False),
        ("utf-8", "ja_JP.UTF-8", False),  # the symbols are wider there
    ],
)
def test_symbols_need_an_encoding_and_locale_that_show_them(monkeypatch, encoding, lang, supported):
    for name in ("LC_ALL", "LC_CTYPE", "LANG"):
        monkeypatch.delenv(name, raising=False)
    if lang:
        monkeypatch.setenv("LANG", lang)
    assert style.symbols_supported(FakeStream(encoding=encoding)) is supported


def test_symbols_fall_back_to_plain_ones():
    assert style.symbol("»", ">") == "»"
    style.use_symbols(False)
    assert style.symbol("»", ">") == ">"


@pytest.mark.parametrize(("columns", "width"), [("40", 39), ("80", 79), ("200", 79)])
def test_lines_stay_within_the_terminal_and_79_columns(monkeypatch, columns, width):
    monkeypatch.setenv("COLUMNS", columns)
    assert style.line_width() == width


class FakeKernel32:
    """Stands in for Windows' kernel32: only the handles in *consoles* are consoles."""

    def __init__(self, consoles):
        self.modes_set = []

        def get_mode(handle, mode):
            if handle not in consoles:
                return 0
            mode._obj.value = 3
            return 1

        def set_mode(handle, mode):
            self.modes_set.append((handle, mode))
            return 1

        # Plain functions, so the code under test can set argtypes on them.
        self.GetStdHandle = lambda handle_id: {-11: 1, -12: 2}[handle_id]
        self.GetConsoleMode = get_mode
        self.SetConsoleMode = set_mode


@pytest.fixture
def windows(monkeypatch):
    """Pretend to be on Windows, with a fake console API; return what was registered at exit."""
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(style.sys, "platform", "win32")
    at_exit = []
    monkeypatch.setattr(style.atexit, "register", lambda *call: at_exit.append(call))

    def use(kernel32):
        monkeypatch.setattr(ctypes, "WinDLL", lambda name: kernel32, raising=False)

    return use, at_exit


def test_windows_consoles_are_asked_for_colors_and_put_back_at_exit(windows):
    use, at_exit = windows
    kernel32 = FakeKernel32(consoles={1})
    use(kernel32)
    assert style.colors_supported(FakeStream())
    assert kernel32.modes_set == [(1, 3 | 0x0004)]
    assert at_exit == [(kernel32.SetConsoleMode, 1, 3)]


def test_no_colors_when_the_windows_console_says_no(windows):
    use, at_exit = windows
    use(FakeKernel32(consoles=set()))
    assert not style.colors_supported(FakeStream())
    assert at_exit == []


def test_no_colors_on_windows_without_the_console_api(windows, monkeypatch):
    monkeypatch.delattr(ctypes, "WinDLL", raising=False)
    assert not style.colors_supported(FakeStream())
