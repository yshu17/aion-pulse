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
    log = tmp_path / "Chat.log"
    write(
        log,
        [
            f"{stamp(20 * 60)} : [2.Торговля] [charname:Old;1 1 1]: давно",
            f"{stamp(10 * 60)} : [3.Поиск группы] [charname:Lfg;1 1 1]: ищу хила",
            f"{stamp(5 * 60)} : Бешеный ветер I: Скор. движ. цели увеличивается.",
            f"{stamp(60)} : [charname:Whisp;0 0 0]: привет",
        ],
        "wb",
    )
    saved = {}
    view = AllChatView(
        root,
        get_path=lambda: str(log),
        names={},
        minutes=minutes,
        show_system=system,
        on_settings=lambda **kw: saved.update(kw),
    )
    view.pack()
    return view, log, saved


def text(view):
    return view.text.get("1.0", "end")


def test_activate_shows_last_minutes_oldest_first_without_system(root, tmp_path):
    view, _log, _ = make(root, tmp_path)
    view.activate()
    t = text(view)
    assert "Old:" not in t
    assert "Бешеный ветер" not in t
    assert t.index("Lfg: ищу хила") < t.index("Whisp: привет")
    assert "[3.Поиск группы]" in t
    view.deactivate()


def test_periods_are_multiples_of_five_up_to_an_hour():
    from watcher.allchat import PERIODS

    assert list(PERIODS.values()) == list(range(5, 61, 5))


def test_system_messages_toggle_and_period_change_reload(root, tmp_path):
    view, _log, saved = make(root, tmp_path)
    view.activate()
    view.system_var.set(True)
    view._on_settings_changed()
    assert "Бешеный ветер" in text(view)
    assert saved == {"minutes": 15, "show_system": True}
    view.minutes_var.set("30 мин")
    view._on_settings_changed()
    assert "Old: давно" in text(view)
    assert saved["minutes"] == 30
    view.deactivate()


def test_live_lines_append_and_pause(root, tmp_path):
    view, log, _ = make(root, tmp_path)
    view.activate()
    write(log, [f"{stamp(0)} : [2.Торговля] [charname:Live;1 1 1]: продам"])
    view._poll()
    assert text(view).rstrip().endswith("Live: продам")
    view.toggle_pause()
    write(log, [f"{stamp(0)} : [2.Торговля] [charname:Late;1 1 1]: ещё"])
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
        minutes=15,
        show_system=False,
        on_settings=lambda **kw: None,
    )
    view.activate()
    assert "не найден" in view.status_var.get()
    view.deactivate()
    assert view._after_id is None
