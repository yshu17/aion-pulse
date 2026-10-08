import tkinter as tk
from datetime import datetime, timedelta

import pytest

from watcher.allchat import AllChatView


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def stamp(ago_sec):
    return (datetime.now() - timedelta(seconds=ago_sec)).strftime("%Y.%m.%d %H:%M:%S")


def write(path, lines, mode="ab"):
    with open(path, mode) as f:
        f.write("".join(line + "\r\n" for line in lines).encode("cp1251"))


def make(root, tmp_path, minutes=15, system=False):
    period = {"minutes": minutes}
    log = tmp_path / "Chat.log"
    write(
        log,
        [
            f"{stamp(20 * 60)} : [3.Поиск группы] [charname:Old;1 1 1]: давно",
            f"{stamp(10 * 60)} : [3.Поиск группы] [charname:Lfg;1 1 1]: ищу хила",
            f"{stamp(5 * 60)} : Получено кинаров: 1 000.",
            f"{stamp(60)} : [charname:Whisp;0.6275 1.0000 0.6275] шепчет: привет",
        ],
        "wb",
    )
    saved = {}
    view = AllChatView(
        root,
        get_path=lambda: str(log),
        names={},
        get_minutes=lambda: period["minutes"],
        show_system=system,
        on_settings=lambda **kw: saved.update(kw),
    )
    view.pack()
    view.period = period
    return view, log, saved


def text(view):
    return view.text.get("1.0", "end")


def test_activate_shows_last_minutes_oldest_first_without_system(root, tmp_path):
    view, _log, _ = make(root, tmp_path)
    view.activate()
    t = text(view)
    assert "Old:" not in t
    assert "Получено кинаров" not in t
    assert t.index("Lfg: ищу хила") < t.index("Whisp: привет")
    assert "[3.Поиск группы]" in t
    view.deactivate()


def test_system_messages_toggle_and_period_change_reload(root, tmp_path):
    view, _log, saved = make(root, tmp_path)
    view.activate()
    view.system_var.set(True)
    view._on_settings_changed()
    assert "Получено кинаров: 1 000." in text(view)
    assert saved == {"show_system": True}
    view.period["minutes"] = 30  # «Old» is 20 min back; the app calls reload() when «История» changes
    view.reload()
    assert "Old: давно" in text(view)
    view.deactivate()


def test_live_lines_append_and_pause(root, tmp_path):
    view, log, _ = make(root, tmp_path)
    view.activate()
    write(log, [f"{stamp(0)} : [3.Поиск группы] [charname:Live;1 1 1]: продам"])
    view._poll()
    assert text(view).rstrip().endswith("Live: продам")
    view.toggle_pause()
    write(log, [f"{stamp(0)} : [3.Поиск группы] [charname:Late;1 1 1]: ещё"])
    view._poll()
    assert "Late:" not in text(view)
    view.toggle_pause()
    view._poll()
    assert "Late: ещё" in text(view)
    view.deactivate()


def test_missing_log_shows_status_and_deactivate_stops_polling(root, tmp_path):
    view = AllChatView(
        root,
        get_path=lambda: str(tmp_path / "none.log"),
        names={},
        get_minutes=lambda: 15,
        show_system=False,
        on_settings=lambda **kw: None,
    )
    view.activate()
    assert "не найден" in view.status_var.get()
    view.deactivate()
    assert view._after_id is None


def test_category_of_player_lines():
    from watcher.allchat import category
    from watcher.parser import parse_any_line

    def cat(rest):
        return category(parse_any_line(f"2026.10.08 12:00:00 : {rest}"))

    assert cat("[3.Поиск группы] [charname:A;1.0000 0.6941 0.6941]: хил") == "Поиск группы"
    assert cat("[3.????? ??????] [charname:A;1.0000 0.6941 0.6941]: dps") == "Поиск группы"
    assert cat("[1.???????] [charname:A;1.0000 0.6941 0.6941]: hi") == "Общий"
    assert cat("[charname:A;1.0000 1.0000 1.0000]: + алик") == "Общий"
    assert cat("[charname:A;0.6275 1.0000 0.6275] шепчет: привет") == "Личное"
    assert cat("[charname:A;0.0196 0.7843 0.8431]: 2 глада") == "Группа"
    assert cat("[charname:A;0.6118 0.9059 0.8627]: ресните") == "Легион"
    assert cat("[2.Торговля] [charname:A;1.0000 0.6941 0.6941]: wts") is None
    assert cat("[charname:A;0.9490 0.3961 0.1333] кричит: prepare") is None


def test_system_toggle_shows_only_info_and_errors():
    from watcher.allchat import is_notice
    from watcher.parser import parse_any_line

    def notice(rest):
        return is_notice(parse_any_line(f"2026.10.08 12:00:00 : {rest}"))

    assert notice("Получено: [item]")
    assert notice("Получено кинаров: 10 000.")
    assert notice("Цель находится слишком далеко.")
    assert notice("Невозможно использовать на данную цель.")
    assert notice("Twistedsister получает: [item].")
    assert notice("[Event] PvP Team Arena registration is open!")
    assert not notice("Бешеный ветер I: Скор. движ. цели Mockoco увеличивается.")
    assert not notice("Разгневанная Гера получает 1 234 ед. урона.")
    assert not notice("Hator ??????? 5 ??. ????? ????.")


def test_view_shows_only_wanted_channels(root, tmp_path):
    log = tmp_path / "Chat.log"
    write(
        log,
        [
            f"{stamp(60)} : [2.Торговля] [charname:Trader;1.0000 0.6941 0.6941]: wts",
            f"{stamp(50)} : [charname:Grp;0.0196 0.7843 0.8431]: в группе",
            f"{stamp(40)} : Получено: [item:1;ver2;;;]",
            f"{stamp(30)} : Разгневанная Гера получает 1 ед. урона.",
        ],
        "wb",
    )
    view = AllChatView(root, get_path=lambda: str(log), names={}, get_minutes=lambda: 15, show_system=True,
                       on_settings=lambda **kw: None)
    view.activate()
    t = text(view)
    assert "Trader" not in t and "урона" not in t
    assert "[Группа] Grp: в группе" in t
    assert "Получено: [item]" in t
    view.deactivate()


def test_zero_minutes_shows_only_new_lines(root, tmp_path):
    view, log, _ = make(root, tmp_path, minutes=0)
    view.activate()
    assert "Lfg:" not in text(view) and "Whisp:" not in text(view)
    write(log, [f"{stamp(0)} : [3.Поиск группы] [charname:Fresh;1 1 1]: новое"])
    view._poll()
    assert "Fresh: новое" in text(view)
    view.deactivate()


def test_toolbar_can_live_outside_the_view(root, tmp_path):
    holder = tk.Frame(root)
    view = AllChatView(
        root,
        get_path=lambda: str(tmp_path / "none.log"),
        names={},
        get_minutes=lambda: 15,
        show_system=False,
        on_settings=lambda **kw: None,
        toolbar_parent=holder,
    )
    assert view.toolbar.master is holder
    assert view.system_var.get() is False
