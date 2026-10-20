from datetime import datetime, timedelta, timezone

from core.schedule.reminder_flow import ReminderPlanner, missed_events, missed_text
from core.schedule.timing import bell_key, end_of, lead_label, time_range

MSK = timezone(timedelta(hours=3))
EVENT = {"day": "wed", "start": "20:00", "end": "21:00", "name": "Инга / Келька"}
WED_2000 = datetime(2026, 10, 14, 20, 0)  # a Wednesday, MSK


def test_lead_reminder_then_start_reminder_each_once():
    planner = ReminderPlanner()
    before = planner.due([EVENT], WED_2000 - timedelta(minutes=4), 5, MSK)
    assert [r.title for r in before] == ["Через 5 мин: Инга / Келька"]
    assert before[0].text == "20:00–21:00 · расписание сервера" and before[0].end == datetime(2026, 10, 14, 21, 0)
    assert planner.due([EVENT], WED_2000 - timedelta(minutes=3), 5, MSK) == []  # announced already
    started = planner.due([EVENT], WED_2000 + timedelta(seconds=30), 5, MSK)
    assert [r.title for r in started] == ["Началось: Инга / Келька"]
    assert planner.due([EVENT], WED_2000 + timedelta(seconds=60), 5, MSK) == []


def test_a_lead_reminder_inside_the_last_minute_gives_way_to_the_start_one():
    assert ReminderPlanner().due([EVENT], WED_2000 - timedelta(seconds=30), 5, MSK) == []


def test_missed_events_go_back_at_most_a_week_and_the_text_lists_five():
    now = datetime(2026, 10, 15, 12, 0)
    assert missed_events([EVENT], None, now) == []
    missed = missed_events([EVENT], now - timedelta(days=30), now)
    assert [at for _e, at in missed] == [datetime(2026, 10, 14, 20, 0)]  # only the last week
    title, text = missed_text(missed * 7, MSK)
    assert title == "Пропущено, пока программа была закрыта: 7"
    assert text.startswith("Инга / Келька (ср 20:00)") and text.endswith(" и ещё 2")


def test_time_helpers():
    assert bell_key(EVENT) == "wed|20:00|Инга / Келька" and lead_label(15) == "15 мин"
    late = {**EVENT, "start": "23:00", "end": "01:00"}
    assert end_of(late, datetime(2026, 10, 14, 23, 0)) == datetime(2026, 10, 15, 1, 0)
    assert time_range(WED_2000, WED_2000 + timedelta(hours=1), MSK) == "20:00–21:00"
