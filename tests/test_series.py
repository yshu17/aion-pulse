from core.chat.parser import ChatMessage
from core.chat.series import SeriesTracker


def msg(nick="Seller", text="wts"):
    return ChatMessage(time="2026.10.09 18:00:00", nick=nick, text=text, raw="")


def test_new_series_rings():
    s = SeriesTracker()
    assert not s.is_silent(msg(), ["Клинок Рудры"], 0)


def test_rings_until_accepted_then_silent():
    s = SeriesTracker()
    s.record(msg(), ["Клинок Рудры"], 0, alert_id=1)
    assert not s.is_silent(msg(), ["Клинок Рудры"], 10)  # first one missed / pending: ring again
    s.record(msg(), ["Клинок Рудры"], 10, alert_id=2)
    assert s.accept(2) == {1}
    assert s.is_silent(msg(), ["Клинок Рудры"], 20)
    assert s.is_silent(msg(nick=" seller "), ["клинок рудры"], 20)  # case and spaces do not matter


def test_other_player_or_other_match_rings():
    s = SeriesTracker()
    s.record(msg(), ["Клинок Рудры"], 0, alert_id=1)
    s.accept(1)
    assert not s.is_silent(msg(nick="Other"), ["Клинок Рудры"], 5)
    assert not s.is_silent(msg(), ["Меч Фланаса"], 5)
    assert not s.is_silent(msg(), ["Клинок Рудры", "Меч Фланаса"], 5)  # one new match is enough
    assert s.is_silent(msg(), ["Клинок Рудры"], 5)


def test_series_ends_after_12_messages():
    s = SeriesTracker()
    s.record(msg(), ["wts"], 0, alert_id=1)
    s.accept(1)
    for i in range(2, 13):  # messages 2..12 of the series are silent
        assert s.is_silent(msg(), ["wts"], i)
        s.record(msg(), ["wts"], i)
    assert not s.is_silent(msg(), ["wts"], 13)  # 13th starts a new series


def test_series_ends_after_15_idle_minutes():
    s = SeriesTracker()
    s.record(msg(), ["wts"], 0, alert_id=1)
    s.accept(1)
    s.record(msg(), ["wts"], 14 * 60)
    assert s.is_silent(msg(), ["wts"], 28 * 60)  # 14 min after the last message
    assert not s.is_silent(msg(), ["wts"], 29 * 60)  # 15 min of silence


def test_new_series_after_end_needs_new_accept():
    s = SeriesTracker()
    s.record(msg(), ["wts"], 0, alert_id=1)
    s.accept(1)
    s.record(msg(), ["wts"], 16 * 60, alert_id=2)  # new series
    assert not s.is_silent(msg(), ["wts"], 16 * 60 + 1)
    assert s.accept(2) == set()


def test_reset_forgets_everything():
    s = SeriesTracker()
    s.record(msg(), ["wts"], 0, alert_id=1)
    s.accept(1)
    s.reset()
    assert not s.is_silent(msg(), ["wts"], 1)


def test_accept_unknown_alert_is_harmless():
    s = SeriesTracker()
    assert s.accept(99) == set()
    assert not s.is_silent(msg(), [], 0)
