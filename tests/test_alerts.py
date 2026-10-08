from watcher.alerts import AlertTracker
from watcher.parser import ChatMessage


def msg(nick="A", text="wts"):
    return ChatMessage(time="2026.10.08 18:43:17", nick=nick, text=text, raw="")


def test_found_counts_every_match_and_pending_only_when_nagging():
    t = AlertTracker(react_sec=30)
    t.add(msg(), ["wts"], now=0, nag=False)
    assert (t.found, t.reacted, t.missed) == (1, 0, 0)
    assert t.pending_ids == []
    a = t.add(msg("B"), ["wts"], now=1, nag=True)
    assert t.found == 2
    assert t.pending_ids == [a]


def test_accept_counts_reacted_once():
    t = AlertTracker(react_sec=30)
    a = t.add(msg(), ["wts"], now=0, nag=True)
    assert t.accept(a) is True
    assert t.accept(a) is False
    assert (t.reacted, t.missed, t.pending_ids) == (1, 0, [])


def test_expire_moves_overdue_alerts_to_missed():
    t = AlertTracker(react_sec=30)
    a = t.add(msg("A"), ["wts"], now=0, nag=True)
    b = t.add(msg("B"), ["wts"], now=20, nag=True)
    assert t.expire(now=29.9) == []
    assert t.expire(now=30) == [a]
    assert t.pending_ids == [b]
    assert t.expire(now=50) == [b]
    assert (t.found, t.reacted, t.missed) == (2, 0, 2)


def test_no_timeout_when_react_sec_is_zero():
    t = AlertTracker(react_sec=0)
    a = t.add(msg(), ["wts"], now=0, nag=True)
    assert t.expire(now=10_000) == []
    assert t.pending_ids == [a]


def test_accept_all_and_reset():
    t = AlertTracker(react_sec=30)
    t.add(msg("A"), ["wts"], now=0, nag=True)
    t.add(msg("B"), ["wts"], now=0, nag=True)
    assert len(t.accept_all()) == 2
    assert (t.found, t.reacted, t.missed) == (2, 2, 0)
    t.reset()
    assert (t.found, t.reacted, t.missed, t.pending_ids) == (0, 0, 0, [])


def test_reset_keeps_pending_alerts_but_zeroes_counters():
    t = AlertTracker(react_sec=30)
    a = t.add(msg(), ["wts"], now=0, nag=True)
    t.reset()
    assert t.pending_ids == [a]
    t.accept(a)
    assert (t.found, t.reacted) == (0, 1)
