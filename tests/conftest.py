import pytest


@pytest.fixture(autouse=True)
def game_is_running(monkeypatch):
    """App tests run without the game: pretend it is running unless a test says otherwise."""
    monkeypatch.setattr("watcher.app.game_running", lambda: True, raising=False)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """SN-9: tests never reach the knowledge base; the update check fails as if offline."""
    def offline(url, method, timeout=10):
        raise OSError("tests run offline")
    monkeypatch.setattr("watcher.app.http_fetch", offline, raising=False)
