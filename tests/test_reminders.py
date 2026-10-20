from datetime import datetime

from core.schedule.reminders import due_reminders, reminder_key, starts_at, week_start

EVENT = {"day": "wed", "start": "20:00", "end": "21:00", "name": "Арена"}
WED_1900 = datetime(2026, 10, 14, 19, 0)  # Wednesday


def test_week_start_is_monday_midnight():
    assert week_start(WED_1900) == datetime(2026, 10, 12, 0, 0)


def test_starts_at_uses_the_event_day_and_time():
    assert starts_at(EVENT, datetime(2026, 10, 12)) == datetime(2026, 10, 14, 20, 0)


def test_event_inside_the_lead_window_is_due():
    due = due_reminders([EVENT], WED_1900, lead_min=5, sent=set())
    assert due == []  # 20:00 is 60 min away
    due = due_reminders([EVENT], datetime(2026, 10, 14, 19, 56), lead_min=5, sent=set())
    assert [d[1]["name"] for d in due] == ["Арена"]


def test_already_announced_occurrence_is_not_repeated():
    at = datetime(2026, 10, 14, 20, 0)
    sent = {reminder_key(EVENT, at)}
    assert due_reminders([EVENT], datetime(2026, 10, 14, 19, 56), lead_min=5, sent=sent) == []


def test_past_event_is_not_due():
    assert due_reminders([EVENT], datetime(2026, 10, 14, 20, 30), lead_min=5, sent=set()) == []


def test_next_week_occurrence_has_its_own_key():
    at_this = datetime(2026, 10, 14, 20, 0)
    at_next = datetime(2026, 10, 21, 20, 0)
    assert reminder_key(EVENT, at_this) != reminder_key(EVENT, at_next)


def test_sorted_by_start_and_negative_lead_rejected():
    later = {"day": "wed", "start": "20:03", "end": "21:00", "name": "Б"}
    due = due_reminders([later, EVENT], datetime(2026, 10, 14, 19, 58), lead_min=10, sent=set())
    assert [d[1]["name"] for d in due] == ["Арена", "Б"]
    try:
        due_reminders([EVENT], WED_1900, lead_min=-1, sent=set())
    except ValueError:
        pass
    else:
        raise AssertionError("negative lead accepted")


def test_occurrences_between_spans_weeks_and_excludes_the_left_edge():
    from core.schedule.reminders import occurrences_between

    sun = {"day": "sun", "start": "21:00", "end": "22:00", "name": "Вс"}
    after = datetime(2026, 10, 14, 20, 0)  # Wednesday 20:00, exactly the start of EVENT: excluded
    until = datetime(2026, 10, 21, 20, 0)  # next Wednesday 20:00: included
    got = occurrences_between([EVENT, sun], after, until)
    assert [(e["name"], at) for e, at in got] == [("Вс", datetime(2026, 10, 18, 21, 0)), ("Арена", datetime(2026, 10, 21, 20, 0))]
    assert occurrences_between([EVENT], until, after) == []
