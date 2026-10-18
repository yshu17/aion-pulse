from watcher.app import plural, split_keywords
from watcher.catalog import local_bestiary_dir


def test_split_keywords():
    assert split_keywords(" хил,  ММК ,,чант , ") == ["хил", "ММК", "чант"]
    assert split_keywords("") == []


def test_plural():
    assert [plural(n, "слово", "слова", "слов") for n in (0, 1, 2, 5, 11, 21, 22, 112)] == [
        "0 слов", "1 слово", "2 слова", "5 слов", "11 слов", "21 слово", "22 слова", "112 слов"]


def test_empty_feed_before_start_names_what_is_looked_for(tmp_path):
    import json
    import tkinter as tk

    from watcher.app import App

    log = tmp_path / "fake_chat.log"
    log.write_bytes(b"")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(log), "keywords": ["ммк", "хил"], "game_check": False}),
                        encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        empty = app.feed.empty
        assert empty.shown and empty.title.cget("text") == "Нажми Start — здесь появятся совпадения"
        assert empty.hint.cget("text").startswith("Ищу: 2 слова")
        app.start()
        assert empty.title.cget("text") == "Слежу — совпадений пока нет"
        app.stop()
        assert empty.title.cget("text").startswith("Нажми Start")
    finally:
        root.destroy()


def test_watching_status_breathes_smoothly_and_stops(tmp_path):
    """ui:21 recheck: «Слежу» breathes in at least 9 frames a second, stops on another status and with reduce_motion."""
    import json
    import time
    import tkinter as tk

    from watcher.app import App

    log = tmp_path / "fake_chat.log"
    log.write_bytes(b"")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(log), "keywords": ["хил"], "game_check": False}), encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        app.cfg.reduce_motion = False
        seen = []
        app._set_status(f"Слежу за {log}")
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            root.update()
            colour = str(app.status_label.cget("foreground"))
            if not seen or seen[-1] != colour:
                seen.append(colour)
            time.sleep(0.01)
        assert len(seen) >= 9, seen
        app._set_status("Не слежу")
        root.update()
        assert str(app.status_label.cget("foreground")) == ""
        app.cfg.reduce_motion = True
        app._set_status(f"Слежу за {log}")
        root.update()
        time.sleep(0.3)
        root.update()
        assert str(app.status_label.cget("foreground")) == ""
    finally:
        app._on_close()


def test_every_icon_only_button_has_a_hint(tmp_path):
    """ui:26 recheck: a button that shows only a picture explains itself on hover (watcher.hint.Hint)."""
    import json
    import tkinter as tk
    from tkinter import ttk

    from watcher.app import App

    log = tmp_path / "fake_chat.log"
    log.write_bytes(b"")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(log), "keywords": ["хил"], "game_check": False}), encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        app._show_settings(True)
        root.update()
        missing, found = [], 0
        stack = [root]
        while stack:
            widget = stack.pop()
            stack.extend(widget.winfo_children())
            if isinstance(widget, (ttk.Button, tk.Button)) and str(widget.cget("image")) \
                    and not str(widget.cget("text")).strip():
                found += 1
                if "_schedule" not in widget.bind("<Enter>"):
                    missing.append(str(widget))
        assert found >= 8  # map: whole map, −, +, to the mark; list: search up/down, reset filter; header button
        assert missing == []
    finally:
        app._on_close()


import pytest as _pytest


@_pytest.mark.parametrize("factor", [1.0, 1.25, 1.5])
def test_minimum_window_fits_the_control_rows_at_windows_scaling(tmp_path, factor):
    """ui:28 recheck: at 125/150 % the minimum window kept 600 px of height and the item list's width only, so the
    keyword field, the search mode, the map theme and the bottom of the side panel were cut."""
    import json
    import tkinter as tk

    from watcher.app import App

    log = tmp_path / "fake_chat.log"
    log.write_bytes(b"")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(log), "keywords": ["хил"], "game_check": False}), encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    base = float(root.tk.call("tk", "scaling"))
    root.tk.call("tk", "scaling", base * factor)
    try:
        app = App(root, cfg_path)
        root.update()
        width, height = root.minsize()
        assert width >= app.control_bar.winfo_reqwidth()
        assert width >= app.map_view.bar.winfo_reqwidth() + 48  # notebook margins around the map bar
        scale = float(root.tk.call("tk", "scaling")) / (96 / 72)
        assert height >= min(round(600 * max(1.0, scale)), root.winfo_screenheight() - 80)
    finally:
        root.tk.call("tk", "scaling", base)  # Tk keeps the scaling for every later window of the process
        app._on_close()


def test_tick_keeps_polling_when_processing_fails(tmp_path):
    import json
    import tkinter as tk

    from watcher.app import App

    log = tmp_path / "fake_chat.log"
    log.write_bytes(b"")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(log), "keywords": ["ммк"]}), encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)

        def boom(_lines):
            raise ValueError("boom")

        app._process = boom
        app.start()
        assert app._after_id is not None
        assert app.status_var.get() == "Ошибка: boom"
        app.stop()
    finally:
        root.destroy()


def test_missing_log_then_reappear_starts_at_end(tmp_path):
    import json
    import tkinter as tk

    from watcher.app import App

    log = tmp_path / "late_chat.log"
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(log), "keywords": ["ммк"]}), encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        beeps = []
        app.notifier.play = lambda *a, **k: beeps.append(1)
        app.start()
        assert app.status_var.get().startswith("Chat.log не найден")
        assert app._after_id is not None
        assert len(beeps) == 0

        fmt = "2026.10.08 18:43:17 : [3.Поиск группы] [charname:{};1.0000 0.6941 0.6941]: WTB ММК\r\n"
        log.write_bytes(fmt.format("Old").encode("cp1251"))
        app._tick()
        assert app.status_var.get().startswith("Слежу за")
        assert len(beeps) == 0

        with open(log, "ab") as f:
            f.write(fmt.format("New").encode("cp1251"))
        app._tick()
        assert len(beeps) == 1
        content = app.text.get("1.0", "end")
        assert "New: WTB ММК" in content
        assert "Old:" not in content
        app.stop()
    finally:
        root.destroy()


def test_watched_item_link_alerts_and_shows_name(tmp_path):
    import json
    import tkinter as tk

    from watcher.app import App

    log = tmp_path / "fake_chat.log"
    log.write_bytes(b"")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"chat_log": str(log), "keywords": [], "watch_items": ["100000893"]}),
        encoding="utf-8",
    )
    line = (
        "2026.10.08 18:43:17 : [3.Поиск группы] [charname:Seller;1.0000 0.6941 0.6941]: "
        "wts [item:100000893;ver2;;;] 5кк\r\n"
    )
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        from watcher.catalog import is_listed

        listed = [item for item in app.watch_items if is_listed(item)]
        assert len(app.item_list.order) == len(listed) >= 49
        assert not any(item.grade in ("common", "rare") for item in app.item_list.by_id.values())
        assert app.item_list.checked == {"100000893"}
        beeps = []
        app.notifier.play = lambda: beeps.append(1)
        app.start()
        with open(log, "ab") as f:
            f.write(line.encode("cp1251"))
        app._tick()
        assert beeps == [1]
        assert "Seller: wts <Клинок Рудры> 5кк" in app.text.get("1.0", "end")

        app.item_list.toggle_item("100000893")
        assert json.loads(cfg_path.read_text(encoding="utf-8"))["watch_items"] == []

        app._select_all_items(True)
        assert len(app.cfg.watch_items) == len(listed)
        app.stop()
    finally:
        root.destroy()


def test_mouse_wheel_scrolls_item_list_from_any_row(tmp_path):
    import json
    import tkinter as tk
    from types import SimpleNamespace

    from watcher.app import App

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(tmp_path / "none.log")}), encoding="utf-8")
    root = tk.Tk()
    try:
        app = App(root, cfg_path)
        root.update()
        canvas = app.item_list.canvas
        wheel = SimpleNamespace(x_root=0, y_root=0, delta=-120)
        # Pretend the pointer is over each widget; no dependence on real screen layout.
        for target in (canvas, app.item_list.search_entry, app.items_holder):
            canvas.yview_moveto(0)
            root.winfo_containing = lambda _x, _y, target=target: target
            app._on_mouse_wheel(wheel)
            assert canvas.yview()[0] > 0, target
        canvas.yview_moveto(0)
        root.winfo_containing = lambda _x, _y: app.text
        app._on_mouse_wheel(wheel)
        assert canvas.yview()[0] == 0
    finally:
        root.destroy()


def test_tooltip_shows_item_spec_and_hides(tmp_path):
    import json
    import tkinter as tk

    from watcher.app import App

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(tmp_path / "none.log")}), encoding="utf-8")
    root = tk.Tk()
    try:
        app = App(root, cfg_path)
        root.update()
        app._show_tooltip("110600968")
        win = app.tooltip.window
        assert win is not None and win.winfo_exists()
        texts = [w.cget("text") for w in _descendants(win) if isinstance(w, tk.Label)]
        assert "Кираса Рудры" in texts
        assert "Можно использовать с 55-го уровня." in texts
        assert "•  Латные сапоги Рудры" in texts
        app._hide_tooltip()
        assert app.tooltip.window is None
    finally:
        root.destroy()


def _descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


def test_start_scans_history_minutes_back(tmp_path):
    import json
    import tkinter as tk
    from datetime import datetime, timedelta

    from watcher.app import App

    now = datetime.now()

    def line(ago, nick):
        stamp = (now - timedelta(seconds=ago)).strftime("%Y.%m.%d %H:%M:%S")
        return f"{stamp} : [3.Поиск группы] [charname:{nick};1 1 1]: WTS ммк\r\n"

    log = tmp_path / "Chat.log"
    log.write_bytes((line(900, "Old") + line(240, "Mid") + line(20, "New")).encode("cp1251"))
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"chat_log": str(log), "keywords": ["ммк"], "history_min": 5}), encoding="utf-8"
    )
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        assert app.history_var.get() == "5 мин"
        from watcher.app import HISTORY_CHOICES

        assert list(HISTORY_CHOICES.values()) == [0, 5, 15, 30, 45, 60]
        beeps = []
        app.notifier.play = lambda: beeps.append(1)
        app.start()
        text = app.text.get("1.0", "end")
        assert "Mid:" in text and "New:" in text and "Old:" not in text
        assert beeps == []  # history is shown, but never alerts
        app.stop()

        app.history_var.set("нет")
        app._on_history_changed()
        assert json.loads(cfg_path.read_text(encoding="utf-8"))["history_min"] == 0
    finally:
        root.destroy()


def test_item_list_grouped_by_category(tmp_path):
    import json
    import tkinter as tk

    from watcher.app import App

    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(tmp_path / "none.log")}), encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        groups = app.item_list.groups
        assert list(groups)[:5] == ["Рудра и Фланас", "Лата", "Кольчуга", "Кожа", "Ткань"]
        assert "Крылья" in groups

        app.item_list.set_group("Лата", True)
        lata = {item.id for item in groups["Лата"]}
        assert lata and lata <= set(app.cfg.watch_items)
        assert json.loads(cfg_path.read_text(encoding="utf-8"))["watch_items"] == app.cfg.watch_items

        weapon = groups["Оружие"][0].id
        app.item_list.toggle_collapsed("Оружие")
        assert app.cfg.collapsed_groups == ["Оружие"]
        assert app.item_list.row_top(weapon) is None
        app.item_list.toggle_collapsed("Оружие")
        assert app.cfg.collapsed_groups == []
        assert app.item_list.row_top(weapon) is not None

        app.item_list.toggle_item(groups["Лата"][0].id)
        assert app.item_list.group_checked("Лата") is False
    finally:
        root.destroy()


def test_sound_choice_and_alert_mode_saved(tmp_path):
    import json
    import tkinter as tk

    from watcher.app import App, SYSTEM_BEEP

    wav = tmp_path / "my alarm.wav"
    wav.write_bytes(b"RIFF")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(tmp_path / "none.log")}), encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        app.notifier.play = lambda: None  # selecting a sound previews it; keep tests quiet
        assert app.sound_var.get() == SYSTEM_BEEP
        assert "Alarm01" in app.sound_choices  # Windows media sounds are offered
        app.sound_var.set("Alarm01")
        app._on_sound_selected()
        assert app.cfg.sound_path.lower().endswith("alarm01.wav")
        assert app.notifier.sound_path == app.cfg.sound_path

        app._set_custom_sound(str(wav))
        assert app.sound_var.get() == "my alarm"
        assert json.loads(cfg_path.read_text(encoding="utf-8"))["sound_path"] == str(wav)

        assert app.mode_var.get() == "Стандартный"
        app.mode_var.set("Назойливый")
        app._on_mode_selected()
        assert json.loads(cfg_path.read_text(encoding="utf-8"))["alert_mode"] == "nag"
    finally:
        root.destroy()


def test_nag_mode_raises_alarm_instead_of_single_beep(tmp_path):
    import json
    import tkinter as tk

    from watcher.app import App

    log = tmp_path / "Chat.log"
    log.write_bytes(b"")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"chat_log": str(log), "keywords": ["ммк"], "alert_mode": "nag"}), encoding="utf-8"
    )
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        beeps, alarms = [], []
        app.notifier.play = lambda: beeps.append(1)
        app.alarm.trigger = lambda entries, popup=True: alarms.append([m.nick for m, _hits in entries])
        app.start()
        line = "2026.10.08 18:43:17 : [3.Поиск группы] [charname:A;1 1 1]: WTB ММК\r\n"
        line += "2026.10.08 18:43:18 : [3.Поиск группы] [charname:B;1 1 1]: продам ммк\r\n"
        with open(log, "ab") as f:
            f.write(line.encode("cp1251"))
        app._tick()
        assert alarms == [["A", "B"]]
        assert beeps == []
        app.stop()
    finally:
        root.destroy()


def _nag_app(tmp_path, **cfg):
    import json
    import tkinter as tk

    from watcher.app import App

    log = tmp_path / "Chat.log"
    log.write_bytes(b"")
    cfg_path = tmp_path / "config.json"
    data = {"chat_log": str(log), "keywords": ["ммк"], "alert_mode": "nag"}
    data.update(cfg)
    cfg_path.write_text(json.dumps(data), encoding="utf-8")
    root = tk.Tk()
    root.withdraw()
    app = App(root, cfg_path)
    calls = []
    app.alarm.trigger = lambda entries, popup=True: calls.append(("ring", popup, len(entries)))
    app.alarm.close = lambda: calls.append(("close",))
    app.alarm.sounding = False
    app.notifier.play = lambda: calls.append(("beep",))

    def say(*nicks):
        text = "".join(
            f"2026.10.08 18:43:1{i} : [3.Поиск группы] [charname:{n};1 1 1]: WTB ММК" + "\r\n"
            for i, n in enumerate(nicks)
        )
        with open(log, "ab") as f:
            f.write(text.encode("cp1251"))
        app._tick()

    return root, app, calls, say


def counters(app):
    return (app.tracker.found, app.tracker.reacted, app.tracker.missed)


def test_nag_rows_accept_counts_reacted_and_silences(tmp_path):
    root, app, calls, say = _nag_app(tmp_path)
    try:
        app.start()
        say("A", "B")
        assert calls == [("ring", False, 2)]  # popup is off by default
        assert counters(app) == (2, 0, 0)
        assert app.found_var.get() == "2"
        first, second = app.tracker.pending_ids
        app.feed.boxes[first].invoke()
        assert counters(app) == (2, 1, 0)
        assert ("close",) not in calls  # still one pending
        app.feed.boxes[second].invoke()
        assert counters(app) == (2, 2, 0)
        assert calls[-1] == ("close",)
        assert app.reacted_var.get() == "2"
        app.stop()
    finally:
        root.destroy()


def test_unaccepted_rows_expire_to_missed(tmp_path):
    root, app, calls, say = _nag_app(tmp_path, react_sec=30)
    try:
        app.start()
        say("A")
        alert_id = app.tracker.pending_ids[0]
        app._ui_tick(now=app.tracker._pending[alert_id].created + 31)
        assert counters(app) == (1, 0, 1)
        assert app.feed.countdowns[alert_id].cget("text") == "пропущено"
        assert app.missed_var.get() == "1"
        assert calls[-1] == ("close",)
        app.stop()
    finally:
        root.destroy()


def test_popup_ack_accepts_all_and_settings_saved(tmp_path):
    import json

    root, app, calls, say = _nag_app(tmp_path, nag_popup=True)
    try:
        assert app.react_var.get() == "30 с"
        app.start()
        say("A", "B")
        assert calls[0] == ("ring", False, 2)  # ui:40: the overlay popup is off, so the alarm does not show it
        app._on_popup_ack()
        assert counters(app) == (2, 2, 0)
        app.react_var.set("60 с")
        app._on_react_selected()
        app.popup_var.set(False)
        app._on_popup_toggled()
        saved = json.loads(app.config_path.read_text(encoding="utf-8"))
        assert (saved["react_sec"], saved["nag_popup"]) == (60, False)
        app.stop()
    finally:
        root.destroy()


def test_counters_always_shown_and_reset(tmp_path):
    root, app, _calls, say = _nag_app(tmp_path, alert_mode="standard", show_counters=False)
    try:
        assert not hasattr(app, "counters_var")  # no on/off checkbox any more
        assert app.counters_bar.winfo_manager() == "pack"  # even with an old «show_counters: false»
        app.start()
        say("A")
        assert counters(app) == (1, 0, 0)
        app._reset_counters()
        assert app.found_var.get() == "0"
        app.stop()
    finally:
        root.destroy()


def test_short_status_indicator_next_to_start(tmp_path):
    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        assert app.counters_bar.master is app.header  # counters in the header
        # UI/UX item 3: Start, the status and the keywords in one always visible row, the game folder in «Настройки»
        assert app.status_label.master is app.control_bar is app.start_btn.master is app.kw_entry.master
        assert app.browse_btn.master is app.settings_card
        assert app.status_short_var.get() == "Не слежу"
        app.start()
        assert app.status_short_var.get().startswith("Слежу")
        app.stop()
        assert app.status_short_var.get() == "Не слежу"
        app.cfg.chat_log = str(tmp_path / "missing.log")
        app.start()
        assert app.status_short_var.get() == "Chat.log не найден"
        app.stop()
    finally:
        root.destroy()


def test_folder_field_shows_full_chat_log_path(tmp_path):
    import json
    from pathlib import Path

    root, app, _calls, _say = _nag_app(tmp_path, chat_log="")
    try:
        game = tmp_path / "Aion Empire"
        app.game_dir_var.set(str(game))
        app._apply_game_dir()
        assert app.cfg.game_dir == str(game) and app.cfg.chat_log == ""
        assert app.game_dir_var.get() == str(game / "classic" / "Chat.log")

        app.game_dir_var.set(str(game / "classic" / "Chat.log"))  # pasting the full path also works
        app._apply_game_dir()
        assert app.cfg.game_dir == str(game) and app.cfg.chat_log == ""

        other = tmp_path / "logs" / "Chat.log"
        app.game_dir_var.set(str(other))
        app._apply_game_dir()
        assert Path(app.cfg.chat_log) == other
        assert json.loads(app.config_path.read_text(encoding="utf-8"))["chat_log"] == str(other)
    finally:
        root.destroy()


def test_volume_slider_sets_and_saves_volume(tmp_path):
    import json

    root, app, _calls, _say = _nag_app(tmp_path, sound_volume=40)
    try:
        assert app.volume_var.get() == 40 and app.notifier.volume == 40
        app.volume_var.set(75)
        app._on_volume_changed()
        assert app.notifier.volume == 75
        assert json.loads(app.config_path.read_text(encoding="utf-8"))["sound_volume"] == 75
    finally:
        root.destroy()


def test_one_history_choice_drives_search_and_all_chat(tmp_path):
    import json

    root, app, _calls, _say = _nag_app(tmp_path, history_min=30)
    try:
        assert app.history_var.get() == "30 мин"
        assert app.all_chat.get_minutes() == 30
        reloads = []
        app.all_chat.reload = lambda: reloads.append(1)
        app.history_var.set("5 мин")
        app._on_history_changed()
        assert app.all_chat.get_minutes() == 5 and reloads == [1]
        assert json.loads(app.config_path.read_text(encoding="utf-8"))["history_min"] == 5
    finally:
        root.destroy()


def test_all_chat_toolbar_sits_in_tab_row_only_on_its_tab(tmp_path):
    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        app.all_chat.activate = lambda: None
        app.all_chat.deactivate = lambda: None
        toolbar = app.all_chat.toolbar
        assert toolbar.master is not app.all_chat
        assert not toolbar.winfo_manager()
        app.tabs.select(app.all_chat)
        app._on_tab_changed()
        assert toolbar.winfo_manager() == "place"
        app.tabs.select(app.search_tab)
        app._on_tab_changed()
        assert not toolbar.winfo_manager()
    finally:
        root.destroy()


def test_all_chat_tab_activates_on_select(tmp_path):
    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        activated = []
        app.all_chat.activate = lambda: activated.append("on")
        app.all_chat.deactivate = lambda: activated.append("off")
        app.tabs.select(app.all_chat)
        app._on_tab_changed()
        app.tabs.select(app.search_tab)
        app._on_tab_changed()
        assert activated == ["on", "off"]
    finally:
        root.destroy()


def test_status_chip_colour_icon_and_one_width(tmp_path):
    from watcher.app import GAME_OFF

    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        widths = set()
        for text, style in (("Остановлен", "Idle"), ("Слежу за X", "Live"), (GAME_OFF, "Warn"),
                            ("Chat.log не найден: X", "Warn"), ("Ошибка чтения: очень длинная причина ошибки", "Error")):
            app._set_status(text)
            root.update()
            assert app.status_label.cget("style") == f"{style}.Chip.TLabel"
            assert app.status_label.cget("image")  # an icon as well as the colour
            assert app.status_hint.text == text  # the full status on hover
            widths.add(app.status_label.winfo_reqwidth())
        assert len(widths) == 1  # the keywords field next to it never jumps
    finally:
        root.destroy()


def test_settings_card_folds_away_and_is_remembered(tmp_path):
    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        root.update()
        assert not app.cfg.settings_open and not app.settings_card.winfo_manager()  # compact first launch
        assert app.settings_btn.cget("text") == "Настройки" and app.settings_btn.cget("image")
        app.cfg.reduce_motion = True  # instant fold; the smooth one has its own test
        app._toggle_settings()
        root.update()
        assert app.settings_card.winfo_manager() == "pack"
        assert '"settings_open": true' in app.config_path.read_text(encoding="utf-8")
        # unfolded again right under the control row, above the tabs
        assert app.settings_card.winfo_y() > app.control_bar.winfo_y()
        assert app.settings_card.winfo_y() < app.tabs.winfo_y()
        app._toggle_settings()
        root.update()
        assert not app.settings_card.winfo_manager() and app.settings_btn.cget("text") == "Настройки"
        assert '"settings_open": false' in app.config_path.read_text(encoding="utf-8")
    finally:
        root.destroy()


def test_fresh_start_keeps_filters_visible_at_600px(tmp_path):
    """ui:3: first launch should leave the content area usable at the minimum height."""
    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        root.update()
        root.minsize(1000, 600)  # same contractual viewport as the snapshot fixture
        root.geometry("1000x600")
        root.deiconify()
        root.update()
        app.settle_layout()  # the tab pages return once a resize settles; tests read the layout now
        root.update()
        assert not app.cfg.settings_open
        assert not app.settings_card.winfo_manager()
        assert app.settings_btn.winfo_ismapped()
        assert root.winfo_width() == 1000
        assert app.item_list.type_box.winfo_ismapped()
        assert (app.item_list.type_box.winfo_rooty() + app.item_list.type_box.winfo_height()
                <= root.winfo_rooty() + root.winfo_height())
    finally:
        root.destroy()


def test_history_matches_are_shown_without_alert(tmp_path):
    import json
    import tkinter as tk
    from datetime import datetime, timedelta

    from watcher.app import App

    CRLF = chr(13) + chr(10)
    stamp = (datetime.now() - timedelta(seconds=60)).strftime("%Y.%m.%d %H:%M:%S")
    log = tmp_path / "Chat.log"
    log.write_bytes((f"{stamp} : [3.Поиск группы] [charname:Past;1 1 1]: WTS ммк" + CRLF).encode("cp1251"))
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"chat_log": str(log), "keywords": ["ммк"], "history_min": 5, "alert_mode": "nag"}),
        encoding="utf-8",
    )
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        rings = []
        app.alarm.trigger = lambda entries, popup=True: rings.append(len(entries))
        app.notifier.play = lambda: rings.append("beep")
        app.start()
        text = app.text.get("1.0", "end")
        assert "Past: WTS ммк" in text
        assert "история за 5 мин" in text
        assert rings == [] and app.tracker.pending_ids == [] and app.tracker.found == 0
        with open(log, "ab") as f:
            f.write((f"{stamp[:11]}23:59:59 : [3.Поиск группы] [charname:Now;1 1 1]: ммк" + CRLF).encode("cp1251"))
        app._tick()
        assert rings == [1] and app.tracker.found == 1
        app.stop()
    finally:
        root.destroy()


def test_reaction_time_has_no_off_option_and_old_zero_becomes_30(tmp_path):
    from watcher.app import REACT_CHOICES

    assert "выкл" not in REACT_CHOICES and 0 not in REACT_CHOICES.values()
    root, app, _calls, _say = _nag_app(tmp_path, react_sec=0)
    try:
        assert app.react_var.get() == "30 с"
        assert app.cfg.react_sec == 30 and app.tracker.react_sec == 30
    finally:
        root.destroy()


def test_search_mode_selector_saved_and_applied(tmp_path):
    import json

    from watcher.app import SEARCH_MODES

    assert list(SEARCH_MODES) == ["Слово ИЛИ предмет", "Только слова", "Только предметы", "Слово И предмет"]
    root, app, calls, say = _nag_app(tmp_path, alert_mode="standard", watch_items=["100000893"])
    try:
        assert app.search_mode_var.get() == "Слово ИЛИ предмет"
        app.search_mode_var.set("Только предметы")
        app._on_search_mode_selected()
        assert json.loads(app.config_path.read_text(encoding="utf-8"))["search_mode"] == "items"
        assert app.matcher.mode == "items"
        app.start()
        say("A")  # «WTB ММК»: keyword only, no item link
        assert calls == []
        app.search_mode_var.set("Слово И предмет")
        app._on_search_mode_selected()
        assert "Слово И предмет" in app.status_var.get() or app.matcher.mode == "and"
        app.stop()
    finally:
        root.destroy()


def test_status_hints_when_search_mode_lacks_input(tmp_path):
    root, app, _calls, _say = _nag_app(tmp_path, keywords=[], watch_items=[], search_mode="and")
    try:
        app.start()
        assert "нет ключевых слов" in app.status_var.get()
        assert "не отмечены предметы" in app.status_var.get()
        app.stop()
    finally:
        root.destroy()


def test_search_mode_disables_unused_inputs(tmp_path):
    root, app, _calls, _say = _nag_app(tmp_path, alert_mode="standard")
    try:
        item_widgets = app.item_controls  # «Все» / «Снять»
        assert len(item_widgets) == 2

        def disabled(widget):
            return widget.instate(["disabled"])

        def select(mode):
            app.search_mode_var.set(mode)
            app._on_search_mode_selected()

        select("Только слова")
        assert all(disabled(w) for w in item_widgets)
        assert app.item_list.enabled is False
        assert not disabled(app.kw_entry)

        select("Только предметы")
        assert disabled(app.kw_entry)
        assert not any(disabled(w) for w in item_widgets)
        assert app.item_list.enabled is True

        for mode in ("Слово И предмет", "Слово ИЛИ предмет"):
            select(mode)
            assert not disabled(app.kw_entry)
            assert not any(disabled(w) for w in item_widgets)
    finally:
        root.destroy()
    root, app, _calls, _say = _nag_app(tmp_path, search_mode="items")  # a saved mode applies on startup
    try:
        assert app.kw_entry.instate(["disabled"])
    finally:
        root.destroy()


def test_search_feed_highlights_item_links_with_tooltip(tmp_path):
    root, app, calls, say = _nag_app(tmp_path, alert_mode="standard", search_mode="items",
                                     watch_items=["110600968"])
    try:
        hovered = []
        app.feed.linker.on_enter = hovered.append
        app.start()
        line = "2026.10.08 18:43:17 : [3.Поиск группы] [charname:S;1 1 1]: wts [item:110600968;ver2;;;]" + chr(13) + chr(10)
        with open(app.cfg.chat_log_path(), "ab") as f:
            f.write(line.encode("cp1251"))
        app._tick()
        text = app.feed.text
        assert "S: wts <Кираса Рудры>" in text.get("1.0", "end")
        start, end = text.tag_ranges("item_110600968")
        assert text.get(start, end) == "<Кираса Рудры>"
        assert "hit" in text.tag_names(start)  # the watched item is also the match
        app.feed.linker.enter("110600968")
        assert hovered == ["110600968"]
        app.stop()
    finally:
        root.destroy()


def _post(app, nick, text):
    line = f"2026.10.09 18:00:00 : [3.Поиск группы] [charname:{nick};1 1 1]: {text}" + chr(13) + chr(10)
    with open(app.cfg.chat_log_path(), "ab") as f:
        f.write(line.encode("cp1251"))
    app._tick()


def _rings(calls):
    return sum(1 for c in calls if c[0] == "ring")


def test_series_rings_until_accepted_then_repeats_are_silent(tmp_path):
    root, app, calls, _say = _nag_app(tmp_path)
    try:
        app.start()
        _post(app, "Leader", "ммк 1/12")
        first = app.tracker.pending_ids[0]
        app._ui_tick(now=app.tracker._pending[first].created + 31)  # first one missed
        _post(app, "Leader", "ммк 2/12")
        assert _rings(calls) == 2  # missed first: the repeat rings as usual
        second = app.tracker.pending_ids[0]
        app._on_feed_accept(second)
        _post(app, "Leader", "ммк 3/12")
        _post(app, "Leader", "ммк 4/12")
        assert _rings(calls) == 2  # accepted: the rest of the series is silent
        assert app.tracker.pending_ids == []
        assert "Уже принято" in app.feed.text.get("1.0", "end")
        assert counters(app) == (4, 1, 1)  # silent repeats are found, not reacted / missed
        _post(app, "Other", "ммк 1/6")
        assert _rings(calls) == 3  # another player rings
    finally:
        root.destroy()


def test_accepting_one_accepts_waiting_alerts_of_same_series(tmp_path):
    root, app, calls, _say = _nag_app(tmp_path)
    try:
        app.start()
        _post(app, "Leader", "ммк 1/12")
        _post(app, "Leader", "ммк 2/12")
        _post(app, "Other", "ммк 1/6")
        assert len(app.tracker.pending_ids) == 3
        first = app.tracker.pending_ids[0]
        app._on_feed_accept(first)
        remaining = app.tracker.pending_ids
        assert len(remaining) == 1  # only the other player's alert still waits
        assert app.tracker._pending[remaining[0]].msg.nick == "Other"
    finally:
        root.destroy()


def test_series_logic_only_in_nag_mode_and_reset_by_stop(tmp_path):
    root, app, calls, _say = _nag_app(tmp_path)
    try:
        app.start()
        _post(app, "Leader", "ммк 1/12")
        app._on_feed_accept(app.tracker.pending_ids[0])
        app.stop()
        app.start()
        _post(app, "Leader", "ммк 2/12")
        assert _rings(calls) == 2  # Stop forgot the accepted series
        app._on_feed_accept(app.tracker.pending_ids[0])
        app.mode_var.set("Стандартный")
        app._on_mode_selected()
        _post(app, "Leader", "ммк 3/12")
        assert ("beep",) in calls  # standard mode beeps as before
    finally:
        root.destroy()


def test_divider_resizes_item_list_with_minimum_widths(tmp_path):
    root, app, _calls, _say = _nag_app(tmp_path, items_width=800)
    try:
        root.deiconify()
        root.geometry("1800x900")
        root.update()
        app.settle_layout()  # the tab pages return once a resize settles; tests read the layout now
        root.update()
        app._init_split()
        assert abs(app.items_panel.winfo_width() - 800) <= 2  # saved width restored
        min_width = app.items_panel.winfo_reqwidth()
        app.set_items_width(100)
        assert app.items_panel.winfo_width() >= min_width - 2  # never narrower than its natural width
        app.set_items_width(5000)
        feed_width = app.split.panes()[0]
        assert root.nametowidget(feed_width).winfo_width() >= min_width - 2  # nor the feed
        app.set_items_width(700)
        app._on_split_moved()
        assert app.cfg.items_width == app.items_panel.winfo_width()
    finally:
        root.destroy()


def test_place_link_opens_map_tab(tmp_path):
    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        root.deiconify()
        root.geometry("1500x950")
        root.update()
        app._open_place("220070000", 1173.0, 1227.4, "Место · Келькмарос")
        root.update()
        assert app.tabs.select() == str(app.map_view)
        assert app.map_view.zone.name == "Келькмарос"
        assert app.map_view.title.cget("text") == "Место · Келькмарос"
    finally:
        root.destroy()


def test_start_refused_and_watching_stopped_when_game_not_running(tmp_path, monkeypatch):
    import watcher.app as app_module

    root, app, _calls, _say = _nag_app(tmp_path)
    beeps = []
    app.notifier.play = lambda *a, **k: beeps.append(1)
    try:
        monkeypatch.setattr(app_module, "game_running", lambda: False)
        app.start()  # game closed: no watching, a warning instead
        assert not app.running
        assert app.status_short_var.get() == "Игра не запущена"
        assert "Игра не запущена" in app.text.get("1.0", "end") and beeps == [1]

        monkeypatch.setattr(app_module, "game_running", lambda: True)
        app.start()
        assert app.running and app.status_short_var.get().startswith("Слежу")
        monkeypatch.setattr(app_module, "game_running", lambda: False)  # the game is closed while watching
        app._last_game_check = -1e9
        app._tick()
        assert not app.running and app._after_id is None
        assert app.status_short_var.get() == "Игра не запущена" and beeps == [1, 1]

        monkeypatch.setattr(app_module, "game_running", lambda: None)  # process list unavailable: keep going
        app.start()
        assert app.running
        app.stop()
        app.cfg.game_check = False  # check switched off in config.json
        monkeypatch.setattr(app_module, "game_running", lambda: False)
        app.start()
        assert app.running
        app.stop()
    finally:
        root.destroy()


def test_overlay_setting_is_disabled_and_does_not_show_a_popup(tmp_path):
    """ui:40: the always-on-top setting is shown disabled and has no effect; the saved value is kept."""
    import json

    from watcher.config import OVERLAY_POPUP_ENABLED

    assert OVERLAY_POPUP_ENABLED is False
    root, app, calls, say = _nag_app(tmp_path, nag_popup=True)
    try:
        assert "disabled" in app.popup_check.state()
        assert app.cfg.nag_popup is True  # the user's saved choice stays in config.json
        app.start()
        say("A")
        assert calls[0] == ("ring", False, 1)
        app.stop()
        assert json.loads(app.config_path.read_text(encoding="utf-8"))["nag_popup"] is True
    finally:
        root.destroy()


def test_settings_button_fits_at_the_minimum_window_width(tmp_path):
    """ui:41 / UI-DEF-1: at 1000 px the keyword entry shrinks; «Настройки» is never cut off the right edge."""
    root, app, calls, say = _nag_app(tmp_path)
    try:
        root.geometry("1000x600")
        root.deiconify()
        root.update()
        bar = app.control_bar
        right = app.settings_btn.winfo_x() + app.settings_btn.winfo_width()
        assert right <= bar.winfo_width() - 8  # inside the bar's right padding
        assert app.kw_entry.winfo_width() >= 80  # the entry still has room to type
    finally:
        root.destroy()


def test_schedule_tab_is_in_the_app(tmp_path):
    """SN-7: «Расписание» remains available after the Bestiary tab."""
    root, app, calls, say = _nag_app(tmp_path)
    try:
        names = [app.tabs.tab(t, "text") for t in app.tabs.tabs()]
        wanted = ["Поиск", "Весь чат", "Карта", "NPC / Бестиарий", "Расписание"]
        assert names == (wanted if local_bestiary_dir() else [n for n in wanted if n != "NPC / Бестиарий"])
        assert len(app.schedule_tab.events) > 0
        assert app.schedule_tab.next_box.winfo_children()
    finally:
        root.destroy()


def test_schedule_reminders_before_and_at_start_once(tmp_path):
    """SN-8: a belled event gives one toast N minutes before and one when it starts; unbelled events stay quiet."""
    import json
    from datetime import datetime

    root, app, calls, say = _nag_app(tmp_path, remind_min=15)
    try:
        sent = []
        app.notifications.notify = lambda source, kind, title, text="", *a, **k: sent.append((source, title))
        app.schedule_tab.events = [{"day": "wed", "start": "20:00", "end": "21:00", "name": "Арена"},
                                   {"day": "wed", "start": "20:05", "end": "21:00", "name": "Тихо"}]
        assert app.schedule_tab.lead_minutes() == 15
        app.schedule_tab.toggle_bell(app.schedule_tab.events[0])
        assert json.loads(app.config_path.read_text(encoding="utf-8"))["remind_events"] == ["wed|20:00|Арена"]
        app._msk_clock = lambda: datetime(2026, 10, 14, 19, 50)  # Wednesday, 10 min before
        app._check_reminders()
        app._check_reminders()  # the next tick: no repeat
        assert sent == [("schedule", "Через 15 мин: Арена")]
        app._msk_clock = lambda: datetime(2026, 10, 14, 20, 0, 30)
        app._check_reminders()
        app._check_reminders()
        assert sent[1:] == [("schedule", "Началось: Арена")]
        app.schedule_tab.lead_var.set("1 час")
        app.schedule_tab._on_lead()
        assert json.loads(app.config_path.read_text(encoding="utf-8"))["remind_min"] == 60
    finally:
        root.destroy()


def test_reminder_has_snooze_repeats_and_stops_after_the_event(tmp_path):
    """SN-8: «Понятно» / «Через 5 мин», repeat while unanswered, no repeat once the event is over."""
    from datetime import datetime

    root, app, calls, say = _nag_app(tmp_path, remind_min=5, remind_events=["wed|20:00|Арена"])
    try:
        app.schedule_tab.events = [{"day": "wed", "start": "20:00", "end": "21:00", "name": "Арена"}]
        app.schedule_tab.belled = {"wed|20:00|Арена"}
        app._msk_clock = lambda: datetime(2026, 10, 14, 19, 56)
        app._check_reminders()
        event = app.notifications.history[-1]
        assert [a.id for a in event.actions] == ["accept", "snooze"]
        assert event.repeat_after == 180
        assert event.id in app._reminder_ids
        app._msk_clock = lambda: datetime(2026, 10, 14, 21, 1)  # the event is over
        app._check_reminders()
        assert not app.notifications.is_active(event)
        assert app._reminder_ids == {}
    finally:
        root.destroy()


def test_missed_reminders_while_closed_come_as_one_toast(tmp_path):
    from datetime import datetime

    root, app, calls, say = _nag_app(tmp_path, remind_events=["wed|20:00|Арена", "thu|02:00|Дер"],
                                      remind_last_check="2026-10-14T19:00:00")
    try:
        app.schedule_tab.events = [{"day": "wed", "start": "20:00", "end": "21:00", "name": "Арена"},
                                   {"day": "thu", "start": "02:00", "end": "04:00", "name": "Дер"},
                                   {"day": "wed", "start": "21:00", "end": "22:00", "name": "Без отметки"}]
        app.schedule_tab.belled = {"wed|20:00|Арена", "thu|02:00|Дер"}
        app.schedule_tab.tz = None
        sent = []
        app.notifications.notify = lambda source, kind, title, text="", *a, **k: sent.append((title, text))
        app._msk_clock = lambda: datetime(2026, 10, 15, 9, 0)  # Thursday morning: both belled events were missed
        app._report_missed_reminders()
        assert len(sent) == 1 and sent[0][0] == "Пропущено, пока программа была закрыта: 2"
        assert "Арена (ср" in sent[0][1] and "Дер (чт" in sent[0][1] and "Без отметки" not in sent[0][1]
        assert app.cfg.remind_last_check == "2026-10-15T09:00:00"
    finally:
        root.destroy()


def test_unavailable_overlay_label_is_grey(tmp_path):
    """ui:40 (visual check 13.10): the disabled setting's label uses the theme's DISABLED colour, not normal text."""
    from tkinter import ttk

    from watcher import theme

    root, app, calls, say = _nag_app(tmp_path)
    try:
        style = app.popup_check.cget("style")
        assert ttk.Style(root).lookup(style, "foreground", ["disabled"]) == theme.DISABLED
    finally:
        root.destroy()


def test_header_gradient_never_runs_behind_header_widgets(tmp_path):
    """ui:31 recheck: Tk labels are opaque, so a gradient behind them shows their rectangles — the tint stays in the
    header's empty top band, above every widget."""
    import json
    import tkinter as tk

    from watcher.app import App

    log = tmp_path / "fake_chat.log"
    log.write_bytes(b"")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"chat_log": str(log), "keywords": ["хил"], "game_check": False}), encoding="utf-8")
    root = tk.Tk()
    root.geometry("1200x700")
    try:
        app = App(root, cfg_path)
        root.update()
        backdrop = app._header_gradient
        lines = backdrop.find_withtag("gradient")
        assert lines  # the tint is there
        top = min(child.winfo_rooty() for child in app.header.winfo_children())
        assert backdrop.winfo_rooty() + max(backdrop.coords(line)[1] for line in lines) < top
        assert backdrop.winfo_width() == root.winfo_width()  # across the window, not only behind the title row
    finally:
        app._on_close()


def test_chat_alerts_go_through_toasts_and_their_accept_accepts_the_rows(tmp_path):
    """SN-4: a nag match is a toast with «Принять»; accepting it accepts the rows and silences; a row accepted in the
    feed closes its toast."""
    root, app, calls, say = _nag_app(tmp_path)
    try:
        app.toasts.pump = lambda: None  # keep the queue for the test
        app.start()
        say("A", "B")
        note = app.notifications.pop_next()
        assert note is not None and note.source == "chat" and [a.id for a in note.actions] == ["accept"]
        app._on_toast_action(note, "accept")
        assert counters(app) == (2, 2, 0)
        assert calls[-1] == ("close",)
        say("C")
        second = app.notifications.pop_next()
        app.feed.boxes[app.tracker.pending_ids[0]].invoke()
        assert not app.notifications.is_active(second)
        app.stop()
    finally:
        root.destroy()


def test_game_off_is_a_toast_with_retry(tmp_path):
    """SN-4: «the game is not running» goes to the center once, with «Проверить снова»; it closes when watching starts."""
    from watcher.app import GAME_OFF

    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        app.toasts.pump = lambda: None
        started = []
        app.start = lambda: started.append(True)
        app._set_status(GAME_OFF)
        note = app.notifications.pop_next()
        assert note is not None and note.source == "status" and [a.id for a in note.actions] == ["retry"]
        app._set_status(GAME_OFF)
        assert app.notifications.pop_next() is None  # no second toast while it stays off
        app._on_toast_action(note, "retry")
        assert started == [True]
        app._set_status("Слежу за Chat.log")
        assert not app.notifications.is_active(note)
    finally:
        root.destroy()


def test_notification_settings_live_in_the_settings_card(tmp_path):
    """SN-5 (moved 13.10, user decision): the notification settings are a block of the «Настройки» card, not a tab —
    sources on/off and sound, place, duration, stack, «не беспокоить»; every change goes to config.json and applies."""
    import json

    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        panel = app.notify_panel
        widget = panel
        while widget is not None and widget is not app.settings_card:
            widget = widget.master
        assert widget is app.settings_card
        assert "Уведомления" not in [app.tabs.tab(t, "text") for t in app.tabs.tabs()]
        panel.sound_vars["chat"].set(False)
        panel.show_vars["schedule"].set(False)
        panel.dnd_var.set(True)
        panel.corner_var.set("Справа сверху")
        panel.duration_var.set("15 с")
        panel.stack_var.set("1")
        panel.changed()
        saved = json.loads(app.config_path.read_text(encoding="utf-8"))
        assert (saved["notify_mute"], saved["notify_off"], saved["notify_dnd"]) == (["chat"], ["schedule"], True)
        assert (saved["notify_corner"], saved["notify_duration"], saved["notify_stack"]) == ("top", 15, 1)
        assert app.notifications.rules["chat"].sound is False and app.notifications.do_not_disturb
        assert (app.toasts.corner, app.toasts.duration, app.toasts.max_visible) == ("top", 15, 1)
    finally:
        app._on_close()


def test_schedule_kind_filter_is_saved(tmp_path):
    """SN-7: hidden kinds of the «Расписание» tab survive a restart."""
    import json

    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        app.schedule_tab.kind_vars["Арены Хаоса и Доблести"].set(False)
        app.schedule_tab.filter_changed()
        assert json.loads(app.config_path.read_text(encoding="utf-8"))["schedule_hidden"] == ["Арены Хаоса и Доблести"]
    finally:
        app._on_close()


def test_schedule_event_opens_its_zone_on_the_map(tmp_path):
    """SN-7: «на карте» of a schedule event selects the «Карта» tab with that zone."""
    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        app._open_zone("220070000")
        assert app.tabs.select() == str(app.map_view)
        assert app.map_view.zone is not None and app.map_view.zone.map_id == "220070000"
    finally:
        app._on_close()


def test_schedule_update_check_tells_and_remembers(tmp_path):
    """SN-9: a changed picture on the site gives a toast with «Открыть статью»; «Понятно» remembers that version, so
    the next start stays quiet; a manual check of an unchanged schedule says it is current."""
    import json

    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        app.toasts.pump = lambda: None
        known = app.schedule_known
        app._on_update_result("ok", "schedule-21ru.jpg|x|y", manual=False)
        note = app.notifications.pop_next()
        assert note.title == "Расписание на сайте обновилось" and [a.id for a in note.actions] == ["site", "accept"]
        app._on_toast_action(note, "accept")
        assert json.loads(app.config_path.read_text(encoding="utf-8"))["schedule_seen"] == "schedule-21ru.jpg|x|y"
        app._on_update_result("ok", "schedule-21ru.jpg|x|y", manual=False)
        assert app.notifications.pop_next() is None
        app._on_update_result("ok", known, manual=True)
        assert app.notifications.pop_next().title == "Расписание актуально"
        app._on_update_result("err", "timed out", manual=True)
        assert "Не удалось" in app.notifications.pop_next().title
    finally:
        app._on_close()


def test_settings_card_folds_smoothly_and_ends_in_the_right_state(tmp_path):
    """Motion: «Настройки» grows and shrinks over ~200 ms; it ends natural-height when open and unpacked when closed;
    a click in the middle reverses from the current height; with reduce_motion it is instant."""
    import time

    root, app, _calls, _say = _nag_app(tmp_path)
    try:
        root.deiconify()
        root.geometry("1200x800")
        app.cfg.reduce_motion = False
        app.cfg.settings_open = True  # ui:3 starts folded; this test opens it first
        app._show_settings(True)
        root.update()
        full = app.settings_card.winfo_height()
        app._toggle_settings()  # close
        assert app.settings_card.winfo_manager() and app._fold is not None  # still shrinking
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            root.update()
            time.sleep(0.01)
        assert not app.settings_card.winfo_manager()
        app._toggle_settings()  # open
        heights = [int(str(app.settings_card.cget("height")))]  # the first frame: the card starts low
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            root.update()
            heights.append(app.settings_card.winfo_height())
            time.sleep(0.01)
        assert heights[0] < full and abs(heights[-1] - full) <= 2
        app.cfg.reduce_motion = True
        app._toggle_settings()
        root.update()
        assert not app.settings_card.winfo_manager()
    finally:
        app._on_close()
