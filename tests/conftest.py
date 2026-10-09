import pytest

from shiritori import stats, style


@pytest.fixture(autouse=True)
def stats_file(tmp_path, monkeypatch):
    """Point the game at a temporary game folder so tests never touch the real stats."""
    (tmp_path / "play.py").touch()
    monkeypatch.setattr(stats, "PACKAGE_FOLDER", tmp_path / "shiritori")
    return tmp_path / "stats.json"


@pytest.fixture(autouse=True)
def plain_terminal(monkeypatch):
    """Print without colors, with the Unicode symbols, on an 80-column terminal."""
    monkeypatch.setenv("COLUMNS", "80")
    style.use_colors(False)
    style.use_symbols(True)
    yield
    style.use_colors(False)
    style.use_symbols(True)
