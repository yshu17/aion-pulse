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


def test_kinds_keep_the_data_order_and_fall_back_to_the_name():
    """SN-7: the filter offers each kind once, in the order of the data; an event without «kind» is its own kind."""
    from watcher.schedule_view import kind_of, kinds
    events = [{"name": "1x1", "kind": "Арены"}, {"name": "Дер"}, {"name": "2x2", "kind": "Арены"}]
    assert kind_of(events[1]) == "Дер"
    assert kinds(events) == ["Арены", "Дер"]


def test_hidden_kinds_are_filtered_out():
    from watcher.schedule_view import visible
    events = [{"name": "1x1", "kind": "Арены"}, {"name": "Дер"}]
    assert visible(events, {"Арены"}) == [{"name": "Дер"}]
    assert visible(events, set()) == events


def test_every_event_in_the_data_file_has_a_kind():
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "schedule.json").read_text(encoding="utf-8"))
    assert all(event.get("kind") for event in data["events"])
    assert {e["kind"] for e in data["events"] if e["name"] in ("1x1", "2x2", "3x3", "Gold Arena")} == {"Арены"}


def test_map_for_picks_the_zone_of_the_side():
    """SN-7 «На карте»: an event in two zones opens the zone of the player's side; one zone — that zone; none — None."""
    from watcher.schedule_view import map_for
    both = {"name": "Ингисон / Келькмарос", "maps": ["210050000", "220070000"]}
    assert map_for(both, "dark") == "220070000"  # Asmodians: Келькмарос
    assert map_for(both, "light") == "210050000"  # Elyos: Ингисон
    assert map_for({"name": "РУ", "maps": ["400010000"]}, "dark") == "400010000"
    assert map_for({"name": "Дер"}, "dark") is None


def test_day_blocks_put_overlaps_on_separate_lanes():
    """Day strip: minutes from midnight (24:00 = 1440) and a lane per overlap; the next free lane is reused."""
    from watcher.schedule_view import day_blocks
    events = [{"day": "wed", "start": "16:00", "end": "18:00", "name": "Дер"},
              {"day": "wed", "start": "17:00", "end": "18:00", "name": "2x2"},
              {"day": "wed", "start": "18:00", "end": "19:00", "name": "3x3"},
              {"day": "wed", "start": "22:00", "end": "24:00", "name": "Поздно"}]
    blocks = day_blocks(events)
    assert [(b[1], b[2], b[3]) for b in blocks] == [(960, 1080, 0), (1020, 1080, 1), (1080, 1140, 0), (1320, 1440, 0)]


def test_day_blocks_cut_an_event_past_midnight_at_the_day_end():
    from watcher.schedule_view import day_blocks
    assert day_blocks([{"day": "wed", "start": "23:00", "end": "01:00", "name": "Ночь"}])[0][1:] == (1380, 1440, 0)
