import json
from datetime import datetime
from pathlib import Path

from watcher import schedule_view


def event(day: str, start: str, end: str, name: str) -> dict:
    return {"day": day, "start": start, "end": end, "name": name}


def test_events_for_day_filters_and_sorts_without_changing_input():
    late = event("mon", "18:00", "19:00", "Поздно")
    other = event("tue", "08:00", "09:00", "Не сегодня")
    early = event("mon", "07:30", "08:00", "Рано")
    events = [late, other, early]

    assert schedule_view.events_for_day(events, "mon") == [early, late]
    assert events == [late, other, early]


def test_today_events_uses_moscow_weekday_at_midnight():
    sunday = event("sun", "23:00", "01:00", "Воскресенье")
    monday = event("mon", "00:00", "00:30", "Понедельник")

    assert schedule_view.today_events([sunday, monday], datetime(2026, 10, 19, 0, 0)) == [monday]


def test_next_events_returns_empty_for_no_events_or_zero_limit():
    now = datetime(2026, 10, 19, 0, 0)
    monday = event("mon", "01:00", "02:00", "Позже")

    assert schedule_view.next_events([], now, 5) == []
    assert schedule_view.next_events([monday], now, 0) == []


def test_next_events_rolls_from_sunday_into_next_week():
    sunday = event("sun", "22:00", "23:00", "Воскресенье")
    monday = event("mon", "00:10", "00:40", "Понедельник")

    assert schedule_view.next_events([sunday, monday], datetime(2026, 10, 18, 23, 30), 2) == [
        (monday, datetime(2026, 10, 19, 0, 10)),
        (sunday, datetime(2026, 10, 25, 22, 0)),
    ]


def test_next_events_includes_previous_week_overnight_event_still_running():
    overnight = event("sun", "23:00", "01:00", "Ночь")
    monday = event("mon", "00:45", "01:15", "Утро")

    assert schedule_view.next_events([monday, overnight], datetime(2026, 10, 19, 0, 30), 2) == [
        (overnight, datetime(2026, 10, 18, 23, 0)),
        (monday, datetime(2026, 10, 19, 0, 45)),
    ]


def test_next_events_includes_running_now_but_not_event_at_its_end():
    ended = event("wed", "19:00", "20:00", "Конец")
    running = event("wed", "20:00", "21:00", "Идёт")
    upcoming = event("wed", "20:45", "21:15", "Скоро")
    events = [upcoming, ended, running]

    assert schedule_view.next_events(events, datetime(2026, 10, 14, 20, 30), 2) == [
        (running, datetime(2026, 10, 14, 20, 0)),
        (upcoming, datetime(2026, 10, 14, 20, 45)),
    ]
    assert schedule_view.next_events([running, upcoming], datetime(2026, 10, 14, 21, 0), 1) == [
        (upcoming, datetime(2026, 10, 14, 20, 45)),
    ]


def test_next_events_accepts_end_24_00_from_schedule_data():
    late = event("mon", "22:00", "24:00", "Late")

    assert schedule_view.next_events([late], datetime(2026, 10, 19, 23, 0), 1) == [
        (late, datetime(2026, 10, 19, 22, 0)),
    ]
    assert schedule_view.next_events([late], datetime(2026, 10, 20, 0, 0), 1) == [
        (late, datetime(2026, 10, 26, 22, 0)),
    ]


def test_schedule_json_events_work_with_the_view():
    source = Path(__file__).resolve().parents[1] / 'data' / 'schedule.json'
    events = json.loads(source.read_text(encoding='utf-8'))['events']

    assert len(events) >= 1
    assert schedule_view.next_events(events, datetime(2026, 10, 19, 23, 0), 5)
