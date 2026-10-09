import io
import os
import sys
import time

import pytest

from shiritori.terminal import PosixKeyboard, TurnPrompt, WindowsKeyboard


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def keys(*sequence, clock=None, seconds_per_key=0.0):
    """Return a read_key function that replays *sequence*, advancing *clock* per key."""
    remaining = list(sequence)

    def read_key():
        if clock:
            clock.now += seconds_per_key
        return remaining.pop(0)

    return read_key


def accept_anything(word):
    return None


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def out():
    return io.StringIO()


def test_returns_the_typed_word_and_time_taken(clock, out):
    with TurnPrompt("Ann (C)", 10, out=out, clock=clock) as prompt:
        word, seconds = prompt.read_word(
            accept_anything, keys(*"cat", "\n", clock=clock, seconds_per_key=0.5)
        )
    assert word == "cat"
    assert seconds == 2.0


def test_accepts_enter_from_any_platform(clock, out):
    with TurnPrompt("Ann (C)", 10, out=out, clock=clock) as prompt:
        word, _ = prompt.read_word(accept_anything, keys(*"cat", "\r"))
    assert word == "cat"


def test_lowercases_letters_and_ignores_other_keys(clock, out):
    arrow_up = "\x1b[A"
    with TurnPrompt("Ann (C)", 10, out=out, clock=clock) as prompt:
        word, _ = prompt.read_word(
            accept_anything, keys("C", "1", "-", " ", arrow_up, "A", "é", "T", "\n")
        )
    assert word == "cat"


@pytest.mark.parametrize("backspace", ["\x7f", "\x08"])
def test_backspace_deletes_the_last_letter(clock, out, backspace):
    with TurnPrompt("Ann (C)", 10, out=out, clock=clock) as prompt:
        word, _ = prompt.read_word(accept_anything, keys(*"cab", backspace, "t", "\n"))
    assert word == "cat"


def test_shows_why_a_word_was_rejected_and_lets_the_player_fix_it(clock, out):
    def check(word):
        return None if word == "cat" else "not in the dictionary"

    with TurnPrompt("Ann (C)", 10, out=out, clock=clock) as prompt:
        word, _ = prompt.read_word(check, keys(*"caat", "\n", "\x7f", "\x7f", "t", "\n"))

    assert word == "cat"
    assert "caat  (not in the dictionary)" in out.getvalue()


def test_the_first_letter_is_already_typed(clock, out):
    with TurnPrompt("Ann", 10, start="C", out=out, clock=clock) as prompt:
        word, _ = prompt.read_word(accept_anything, keys(*"at", "\n"))
    assert word == "cat"
    assert "\r 10 | Ann: C" in out.getvalue()
    assert "\r 10 | Ann: Cat" in out.getvalue()


def test_backspace_cannot_remove_the_first_letter(clock, out):
    with TurnPrompt("Ann", 10, start="c", out=out, clock=clock) as prompt:
        word, _ = prompt.read_word(accept_anything, keys("\x7f", "\x7f", *"at", "\n"))
    assert word == "cat"


def test_typing_the_first_letter_again_is_forgiven(clock, out):
    def check(word):
        return None if word in ("cat", "eel") else "not in the dictionary"

    with TurnPrompt("Ann", 10, start="c", out=out, clock=clock) as prompt:
        word, _ = prompt.read_word(check, keys(*"cat", "\n"))
    assert word == "cat"
    with TurnPrompt("Ann", 10, start="e", out=out, clock=clock) as prompt:
        word, _ = prompt.read_word(check, keys(*"el", "\n"))
    assert word == "eel"  # a word that really does start with the letter twice


def test_the_computer_types_the_rest_of_the_word(clock, out):
    pauses = []

    def sleep(seconds):
        pauses.append(seconds)
        clock.now += seconds

    with TurnPrompt("Bot", 10, start="c", out=out, clock=clock) as prompt:
        seconds = prompt.type_word("cat", [1.0, 0.25, 0.5], sleep=sleep)
    assert prompt.text == "cat"
    assert pauses == [1.0, 0.25, 0.5]
    assert seconds == 1.75
    assert ": Ca" in out.getvalue()


def test_draws_the_countdown_and_typed_text(clock, out):
    with TurnPrompt("Ann (C)", 10, out=out, clock=clock) as prompt:
        prompt.read_word(accept_anything, keys(*"ca", "t", "\n"))
    assert "\r 10 | Ann (C): cat" in out.getvalue()


def test_countdown_can_show_something_else(clock, out):
    def points(elapsed):
        return f"{10 - int(elapsed // 2):+d}"

    with TurnPrompt("Ann (C)", 20, countdown=points, out=out, clock=clock) as prompt:
        prompt.read_word(accept_anything, keys(*"cat", "\n", clock=clock, seconds_per_key=1.5))
    assert "\r+10 | Ann (C): c" in out.getvalue()
    assert "\r +9 | Ann (C): ca" in out.getvalue()
    assert "\r +8 | Ann (C): cat" in out.getvalue()


def test_clears_the_line_when_done(clock, out):
    with TurnPrompt("Ann (C)", 10, out=out, clock=clock) as prompt:
        prompt.read_word(accept_anything, keys(*"cat", "\n"))
    assert out.getvalue().endswith("\r" + " " * len(" 10 | Ann (C): cat") + "\r")


@pytest.mark.parametrize(
    ("elapsed", "remaining"),
    [(0, 10), (0.5, 10), (9.5, 1), (10, 0), (10.5, 0), (11.5, -1), (25, -15)],
)
def test_countdown_keeps_going_past_zero(clock, out, elapsed, remaining):
    prompt = TurnPrompt("Ann (C)", 10, out=out, clock=clock)
    clock.now = elapsed
    assert prompt.remaining() == remaining


def test_type_word_types_one_letter_at_a_time(clock, out):
    pauses = []

    def sleep(seconds):
        pauses.append(seconds)
        clock.now += seconds

    with TurnPrompt("Bot (C)", 10, out=out, clock=clock) as prompt:
        seconds = prompt.type_word("cat", [1.0, 0.25, 0.25, 0.5], sleep=sleep)

    assert prompt.text == "cat"
    assert pauses == [1.0, 0.25, 0.25, 0.5]
    assert seconds == 2.0
    assert ": c" in out.getvalue()
    assert ": ca" in out.getvalue()


class FakeConsole:
    """Stands in for Windows' msvcrt module."""

    def __init__(self, *keys):
        self.keys = list(keys)

    def getwch(self):
        return self.keys.pop(0)

    def kbhit(self):
        return bool(self.keys)


def test_windows_keyboard_reads_keys():
    keyboard = WindowsKeyboard(FakeConsole("c", "\r", "\x08"))
    with keyboard:
        assert [keyboard.read_key() for _ in range(3)] == ["c", "\r", "\x08"]


def test_windows_keyboard_reads_arrow_keys_whole():
    keyboard = WindowsKeyboard(FakeConsole("\xe0", "H", "\x00", ";", "a"))
    assert keyboard.read_key() == "\xe0H"
    assert keyboard.read_key() == "\x00;"
    assert keyboard.read_key() == "a"


def test_windows_keyboard_ctrl_c_quits():
    with pytest.raises(KeyboardInterrupt):
        WindowsKeyboard(FakeConsole("\x03")).read_key()


def test_windows_keyboard_discards_early_keys():
    console = FakeConsole("x", "y")
    WindowsKeyboard(console).discard_pending()
    assert console.keys == []


posix_only = pytest.mark.skipif(sys.platform == "win32", reason="needs a POSIX terminal")


@pytest.fixture
def terminal():
    """A pseudo-terminal: write keys to the first file descriptor, read them from the second."""
    import pty

    controller, device = pty.openpty()
    yield controller, device
    os.close(controller)
    os.close(device)


@posix_only
def test_posix_keyboard_reads_one_key_at_a_time(terminal):
    controller, device = terminal
    with PosixKeyboard(device) as keyboard:
        os.write(controller, b"cat\r\x7f")
        assert [keyboard.read_key() for _ in range(5)] == ["c", "a", "t", "\n", "\x7f"]


@posix_only
def test_posix_keyboard_reads_escape_sequences_whole(terminal):
    controller, device = terminal
    with PosixKeyboard(device) as keyboard:
        os.write(controller, b"\x1b[A")
        assert keyboard.read_key() == "\x1b[A"
        os.write(controller, b"\x1b[1;5C")
        assert keyboard.read_key() == "\x1b[1;5C"
        os.write(controller, b"\x1bOP")
        assert keyboard.read_key() == "\x1bOP"
        os.write(controller, b"\x1b")
        assert keyboard.read_key() == "\x1b"


@posix_only
def test_posix_keyboard_does_not_echo_and_restores_the_terminal(terminal):
    import termios

    controller, device = terminal
    before = termios.tcgetattr(device)
    with PosixKeyboard(device) as keyboard:
        assert not termios.tcgetattr(device)[3] & termios.ECHO
        os.write(controller, b"z")
        assert keyboard.read_key() == "z"
    after = termios.tcgetattr(device)
    # macOS may set PENDIN, a flag the kernel keeps for its own bookkeeping.
    pendin = getattr(termios, "PENDIN", 0)
    after[3] &= ~pendin
    before[3] &= ~pendin
    assert after == before


@posix_only
def test_posix_keyboard_discards_early_keys(terminal):
    controller, device = terminal
    with PosixKeyboard(device) as keyboard:
        os.write(controller, b"early")
        time.sleep(0.05)
        keyboard.discard_pending()
        os.write(controller, b"n")
        assert keyboard.read_key() == "n"
