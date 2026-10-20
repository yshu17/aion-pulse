from datetime import datetime, timedelta

import pytest

from core.chat.session import HISTORY, LOUD, QUIET, LogFeed, WatchSession


def line(nick, text, at="2026.10.20 18:00:00"):
    return f"{at} : [3.Поиск группы] [charname:{nick};1.0000 0.6941 0.6941]: {text} "


def session(**kwargs):
    kwargs.setdefault("keywords", ["wts"])
    return WatchSession({"7": "Кираса Рудры"}, {"220070000": "Келькмарос"}, {}, cooldown_sec=0, **kwargs)


def test_standard_mode_counts_matches_and_announces_nothing_pending():
    s = session()
    batch = s.process([line("A", "wts меч"), line("B", "просто текст"), "мусор"], now=1.0)
    assert [(e.msg.nick, e.hits, e.kind, e.alert_id) for e in batch.entries] == [("A", ["wts"], LOUD, None)]
    assert batch.loud[0][0].nick == "A" and batch.announce == []
    assert s.counters == (1, 0, 0) and s.pending_ids == []


def test_watched_items_match_by_link_and_the_mode_combines_them():
    s = session(watch_items={"7": "Кираса Рудры"}, mode="and")
    assert s.process([line("A", "wts [item:7;ver2;;;]"), line("B", "wts без ссылки")], 1.0).entries[0].hits == [
        "wts", "Кираса Рудры"]
    s.set_mode("items")
    s.set_keywords([])
    assert [e.msg.nick for e in s.process([line("C", "[item:7;ver2;;;]")], 2.0).entries] == ["C"]


def test_history_lists_matches_without_counting_or_alerting():
    s = session(alert_mode="nag")
    batch = s.history([line("A", "wts щит")], 1.0)
    assert [e.kind for e in batch.entries] == [HISTORY] and s.counters == (0, 0, 0) and s.pending_ids == []


def test_nag_mode_keeps_alerts_pending_and_announces_each_once():
    s = session(alert_mode="nag")
    first = s.process([line("A", "wts 1/12"), line("B", "wts лук")], 1.0)
    ids = [e.alert_id for e in first.entries]
    assert all(ids) and first.announce == ids and s.pending_ids == ids
    second = s.process([line("C", "wts шлем")], 2.0)
    assert second.announce == [second.entries[0].alert_id]  # the first two were announced already
    assert s.remaining(2.0)[ids[0]] == pytest.approx(29.0)


def test_accepting_one_alert_accepts_its_series_and_later_repeats_come_quiet():
    s = session(alert_mode="nag")
    a1 = s.process([line("A", "wts 1/12")], 1.0).entries[0].alert_id
    a2 = s.process([line("A", "wts 2/12")], 2.0).entries[0].alert_id
    assert s.accept(a1) == [a1, a2] and s.pending_ids == []
    quiet = s.process([line("A", "wts 3/12")], 3.0)
    assert [e.kind for e in quiet.entries] == [QUIET] and quiet.announce == [] and quiet.loud == []
    assert s.counters == (3, 2, 0)
    s.stop()  # a new Start: the series begins again and rings
    assert s.process([line("A", "wts 4/12")], 4.0).entries[0].kind == LOUD


def test_unaccepted_alerts_expire_as_missed_and_accept_all_takes_the_rest():
    s = session(alert_mode="nag", react_sec=10)
    a, b = (e.alert_id for e in s.process([line("A", "wts x")], 0.0).entries + s.process([line("B", "wts y")], 5.0).entries)
    assert s.expire(10.0) == [a] and s.counters == (2, 0, 1)
    assert s.accept_all() == [b] and s.counters == (2, 1, 1)
    s.reset_counters()
    assert s.counters == (0, 0, 0)


def test_place_links_become_pins_with_the_message_as_note():
    s = session()
    batch = s.process([line("A", "тут [pos:Место;220070000 2010.1 1315.8 0.0 0]", at="2026.10.20 18:05:00")], 1.0)
    place = batch.places[0]
    assert (place.map_id, place.x, place.y, place.label) == ("220070000", 2010.1, 1315.8, "Место · Келькмарос")
    assert place.note == "18:05  A: тут <Место · Келькмарос>"
    assert batch.entries == []  # a pin is remembered even without a match


def test_log_feed_reads_history_once_then_new_lines_and_restarts_after_a_missing_file(tmp_path):
    log = tmp_path / "Chat.log"
    now = datetime(2026, 10, 20, 18, 30)
    old, recent = now - timedelta(minutes=90), now - timedelta(minutes=5)
    log.write_bytes((f"{old:%Y.%m.%d %H:%M:%S} : старое\r\n{recent:%Y.%m.%d %H:%M:%S} : свежее\r\n").encode("cp1251"))
    feed = LogFeed(str(log), history_min=60, clock=lambda: now)
    history, lines = feed.poll()
    assert history == [f"{recent:%Y.%m.%d %H:%M:%S} : свежее"] and lines == []
    with log.open("ab") as out:
        out.write("2026.10.20 18:31:00 : новое\r\n".encode("cp1251"))
    assert feed.poll() == (None, ["2026.10.20 18:31:00 : новое"])
    missing = LogFeed(str(tmp_path / "none.log"))
    with pytest.raises(FileNotFoundError):
        missing.poll()
