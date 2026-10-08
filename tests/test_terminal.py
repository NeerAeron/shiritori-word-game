import io

import pytest

from shiritori.terminal import TurnPrompt


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


def test_draws_the_countdown_and_typed_text(clock, out):
    with TurnPrompt("Ann (C)", 10, out=out, clock=clock) as prompt:
        prompt.read_word(accept_anything, keys(*"ca", "t", "\n"))
    assert "\r 10 | Ann (C): cat" in out.getvalue()


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
