import pytest


@pytest.fixture(autouse=True)
def stats_file(tmp_path, monkeypatch):
    """Keep every test's stats in a temporary file instead of the real one."""
    path = tmp_path / "stats.json"
    monkeypatch.setenv("SHIRITORI_STATS_FILE", str(path))
    return path
