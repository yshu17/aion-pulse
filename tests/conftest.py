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


@pytest.fixture(autouse=True)
def mouse_button_is_up(monkeypatch):
    """A window resize while the real mouse button is held freezes the window (the edge drag). The tests must not depend
    on the physical mouse: the button is up unless a test says otherwise."""
    monkeypatch.setattr("watcher.app.primary_button_down", lambda: False, raising=False)
