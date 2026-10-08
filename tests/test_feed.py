import tkinter as tk

import pytest

from watcher.feed import MatchFeed
from watcher.parser import ChatMessage


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def msg(nick, text, time="2026.10.08 18:43:17"):
    return ChatMessage(time=time, nick=nick, text=text, raw="")


def lines(feed):
    return [line for line in feed.text.get("1.0", "end").splitlines() if line.strip()]


def test_rows_append_at_bottom(root):
    feed = MatchFeed(root, on_accept=lambda _id: None)
    feed.add(msg("A", "first"), ["first"])
    feed.add(msg("B", "second"), ["second"])
    rows = lines(feed)
    assert rows[0].endswith("A: first") and rows[1].endswith("B: second")


def test_pending_row_has_accept_checkbox_and_blinks(root):
    accepted = []
    feed = MatchFeed(root, on_accept=accepted.append)
    feed.add(msg("A", "wts"), ["wts"], alert_id=7)
    box = feed.boxes[7]
    assert box.cget("text") == "принять"
    assert feed.text.tag_ranges("blink")
    colors = {feed.text.tag_cget("blink", "background")}
    feed.blink()
    colors.add(feed.text.tag_cget("blink", "background"))
    assert len(colors) == 2
    box.invoke()
    assert accepted == [7]


def test_mark_accepted_and_missed_stop_blinking(root):
    feed = MatchFeed(root, on_accept=lambda _id: None)
    feed.add(msg("A", "wts"), ["wts"], alert_id=1)
    feed.add(msg("B", "wts"), ["wts"], alert_id=2)
    feed.mark(1, "accepted")
    assert feed.boxes[1].cget("text") == "принято"
    assert str(feed.boxes[1].cget("state")) == "disabled"
    feed.mark(2, "missed")
    assert feed.boxes[2].cget("text") == "пропущено"
    assert not feed.text.tag_ranges("blink")


def test_old_rows_are_trimmed(root):
    feed = MatchFeed(root, on_accept=lambda _id: None, max_rows=3)
    for i in range(5):
        feed.add(msg(f"N{i}", "wts"), ["wts"], alert_id=i)
    rows = lines(feed)
    assert len(rows) == 3 and rows[0].endswith("N2: wts")
    assert set(feed.boxes) == {2, 3, 4}
