import pytest

from shiritori import stats


@pytest.fixture(autouse=True)
def stats_file(tmp_path, monkeypatch):
    """Point the game folder at a temporary one so tests never touch the real stats."""
    monkeypatch.setattr(stats, "GAME_FOLDER", tmp_path)
    return tmp_path / "stats.json"
