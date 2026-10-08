import pytest

from shiritori import stats


@pytest.fixture(autouse=True)
def stats_file(tmp_path, monkeypatch):
    """Point the game at a temporary game folder so tests never touch the real stats."""
    (tmp_path / "play.py").touch()
    monkeypatch.setattr(stats, "PACKAGE_FOLDER", tmp_path / "shiritori")
    return tmp_path / "stats.json"
