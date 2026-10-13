"""SN-7: the «Расписание» tab — times in MSK logic, shown in local time, running/next events and a weekday list."""

import tkinter as tk
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from watcher import schedule_tab as st

MSK = timezone(timedelta(hours=3))
WARSAW_SUMMER = timezone(timedelta(hours=2))
EVENTS = [
    {"day": "wed", "start": "20:00", "end": "21:00", "name": "Арена"},
    {"day": "wed", "start": "22:00", "end": "24:00", "name": "Поздно"},
    {"day": "thu", "start": "02:00", "end": "04:00", "name": "Дер"},
]
WED_2030 = datetime(2026, 10, 14, 20, 30)  # a Wednesday, MSK


def test_msk_now_and_local_conversion():
    assert st.msk_now(datetime(2026, 10, 14, 17, 30, tzinfo=timezone.utc)) == WED_2030
    assert st.to_local(WED_2030, WARSAW_SUMMER).strftime("%H:%M") == "19:30"


def test_end_of_handles_24_00_and_overnight():
    start = datetime(2026, 10, 14, 22, 0)
    assert st.end_of({"end": "24:00"}, start) == datetime(2026, 10, 15, 0, 0)
    assert st.end_of({"end": "01:00"}, datetime(2026, 10, 14, 23, 0)) == datetime(2026, 10, 15, 1, 0)


def test_until_text():
    start, end = datetime(2026, 10, 14, 20, 0), datetime(2026, 10, 14, 21, 0)
    assert st.until_text(start, end, WED_2030) == "идёт · ещё 30 мин"
    assert st.until_text(datetime(2026, 10, 14, 22, 0), end, WED_2030) == "через 1 ч 30 мин"
    assert st.until_text(datetime(2026, 10, 14, 20, 45), end, WED_2030) == "через 15 мин"
    assert st.until_text(datetime(2026, 10, 16, 21, 0), end, WED_2030) == "через 2 дн"


def test_time_range_is_local():
    assert st.time_range(datetime(2026, 10, 14, 20, 0), datetime(2026, 10, 14, 21, 0), WARSAW_SUMMER) == "19:00–20:00"


def test_load_events_missing_file_is_empty(tmp_path):
    assert st.load_events(tmp_path / "nope.json") == []
    real = st.load_events(Path(__file__).resolve().parents[1] / "data" / "schedule.json")
    assert len(real) >= 1 and {"day", "start", "end", "name"} <= set(real[0])


def _labels(box):
    return [[w.cget("text") for w in row.winfo_children()] for row in box.winfo_children()]


def test_tab_shows_running_next_and_the_day():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    try:
        from watcher import theme
        theme.apply_dark_theme(root)
        tab = st.ScheduleTab(root, EVENTS, clock=lambda: WED_2030, tz=MSK)
        rows = _labels(tab.next_box)
        assert rows[0] == ["20:00–21:00", "Арена", "идёт · ещё 30 мин"]
        assert rows[1] == ["22:00–00:00", "Поздно", "через 1 ч 30 мин"]
        assert tab.day_var.get() == "Среда"
        assert [r[-1] for r in _labels(tab.day_list)] == ["Арена", "Поздно"]
        tab.day_var.set("Четверг")
        tab.refresh()
        assert [r[-1] for r in _labels(tab.day_list)] == ["Дер"]
        tab.destroy()
    finally:
        root.destroy()


def test_empty_schedule_says_so():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    try:
        from watcher import theme
        theme.apply_dark_theme(root)
        tab = st.ScheduleTab(root, [], clock=lambda: WED_2030, tz=MSK)
        assert _labels(tab.next_box)[0][1] == "Расписание пусто"
        assert _labels(tab.day_list)[0][1] == "В этот день событий нет"
    finally:
        root.destroy()


def test_zone_name_follows_the_moment():
    assert st.zone_name(WED_2030, MSK) == "МСК"
    assert st.zone_name(WED_2030, WARSAW_SUMMER) == "UTC+2"
    assert st.zone_name(WED_2030, timezone(timedelta(hours=5, minutes=30))) == "UTC+5:30"


def test_long_day_scrolls_in_a_low_window():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    try:
        from watcher import theme
        theme.apply_dark_theme(root)
        many = [{"day": "sat", "start": f"{h:02d}:00", "end": f"{h:02d}:30", "name": f"Событие {h}"} for h in range(12)]
        tab = st.ScheduleTab(root, many, clock=lambda: datetime(2026, 10, 17, 1, 0), tz=MSK)  # a Saturday
        tab.pack(fill="both", expand=True)
        root.geometry("600x260")
        root.update()
        assert len(tab.day_list.winfo_children()) == 12
        top = tab.day_canvas.yview()[0]
        tab.scroll(3)
        root.update()
        assert tab.day_canvas.yview()[0] > top  # the list moved: the last events are reachable
    finally:
        root.destroy()
