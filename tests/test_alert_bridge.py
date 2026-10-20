"""SN-4: chat alerts and the «game is not running» status go through the notification center (no Tk here)."""

from core.notify.alert_bridge import AlertBridge
from core.notify.notify_center import NotificationCenter


def make():
    sounds = []
    center = NotificationCenter(sound=sounds.append, clock=lambda: 0.0)
    return AlertBridge(center), center, sounds


def test_a_chat_match_becomes_one_toast_with_the_first_message():
    bridge, center, sounds = make()
    note = bridge.chat_match([1, 2], [("Nick", "ищу группу в данж", ["группу"]), ("Other", "группа на босса", ["группа"])],
                             nag=False)
    assert note.source == "chat" and center.pop_next() is note
    assert "группу" in note.title
    assert note.text.startswith("Nick: ищу группу") and "ещё 1" in note.text
    assert sounds == [note]  # standard mode: the center plays the one beep (its per-source sound rule applies)


def test_nag_mode_offers_accept_and_leaves_the_sound_to_the_alarm_loop():
    bridge, center, sounds = make()
    note = bridge.chat_match([7], [("Nick", "wts", ["wts"])], nag=True)
    assert [a.id for a in note.actions] == ["accept"]
    assert sounds == []  # the nag alarm loops its own sound until the user reacts


def test_accepting_the_toast_returns_its_alerts():
    bridge, center, _ = make()
    note = bridge.chat_match([3, 4], [("A", "x", ["x"]), ("B", "y", ["y"])], nag=True)
    assert bridge.toast_accepted(note) == [3, 4]
    assert bridge.toast_accepted(note) == []  # once


def test_alerts_finished_in_the_feed_close_their_toast():
    bridge, center, _ = make()
    note = bridge.chat_match([5, 6], [("A", "x", ["x"]), ("B", "y", ["y"])], nag=True)
    bridge.alerts_done([5])
    assert center.is_active(note)  # one alert still waits
    bridge.alerts_done([6])
    assert not center.is_active(note)


def test_disabled_chat_source_gives_no_toast_and_no_mapping():
    bridge, center, _ = make()
    center.set_source("chat", enabled=False)
    assert bridge.chat_match([1], [("A", "x", ["x"])], nag=True) is None
    assert bridge.toast_accepted(None) == []


def test_game_off_notifies_once_and_closes_when_the_game_is_back():
    bridge, center, _ = make()
    first = bridge.game_running(False)
    assert first is not None and [a.id for a in first.actions] == ["retry"]
    assert bridge.game_running(False) is None  # no repeat while it stays off
    bridge.game_running(True)
    assert not center.is_active(first)
    assert bridge.game_running(False) is not None  # off again — a new toast
