import pytest


@pytest.fixture(autouse=True)
def game_is_running(monkeypatch):
    """App tests run without the game: pretend it is running unless a test says otherwise."""
    monkeypatch.setattr("watcher.app.game_running", lambda: True, raising=False)
