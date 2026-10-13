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


def test_kind_filter_hides_events_and_reports_the_choice():
    """SN-7: «Виды» — a hidden kind leaves both lists; the choice is handed to the app to save."""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    try:
        from watcher import theme
        theme.apply_dark_theme(root)
        saved = []
        tab = st.ScheduleTab(root, EVENTS, clock=lambda: WED_2030, tz=MSK, hidden={"Арена"}, on_filter=saved.append)
        assert "Арена" not in [r[1] for r in _labels(tab.next_box)]
        assert tab.kind_vars["Арена"].get() is False
        tab.kind_vars["Арена"].set(True)
        tab.kind_vars["Поздно"].set(False)
        tab.filter_changed()
        assert saved[-1] == {"Поздно"}
        names = [r[1] for r in _labels(tab.next_box)]
        assert "Арена" in names and "Поздно" not in names
        assert "1 скрыт" in tab.kinds_button.cget("text")
        tab.destroy()
    finally:
        root.destroy()


def test_own_events_can_be_added_edited_and_removed(tmp_path):
    """SN-7: «Добавить событие», a click on an event opens the form with «Удалить»; changes go to schedule_custom.json."""
    import tkinter as tk
    from watcher.schedule_custom import Custom
    root = tk.Tk()
    root.withdraw()
    try:
        from watcher import theme
        theme.apply_dark_theme(root)
        custom = Custom.load(tmp_path / "schedule_custom.json")
        tab = st.ScheduleTab(root, EVENTS, clock=lambda: WED_2030, tz=MSK, custom=custom)
        form = tab.open_form()
        form.day_var.set("Среда")
        form.start_var.set("23:30")
        form.end_var.set("23:45")
        form.name_var.set("")
        form.save()
        assert "название" in form.error.cget("text") and form.winfo_exists()  # nothing saved, the form explains
        form.name_var.set("Рейд гильдии")
        form.save()
        assert "Рейд гильдии" in [r[-1] for r in _labels(tab.day_list)]
        assert "Свои" in tab.kind_vars
        mine = next(e for e in tab.events if e["name"] == "Рейд гильдии")
        form = tab.open_form(mine)
        assert form.name_var.get() == "Рейд гильдии"
        form.delete()
        assert "Рейд гильдии" not in [r[-1] for r in _labels(tab.day_list)]
        arena = next(e for e in tab.events if e["name"] == "Арена")
        form = tab.open_form(arena)
        form.start_var.set("20:15")
        form.save()
        assert any(e["name"] == "Арена" and e["start"] == "20:15" for e in tab.events)
        assert Custom.load(tmp_path / "schedule_custom.json").data["removed"]  # the data event is hidden, not changed
        tab.destroy()
    finally:
        root.destroy()
