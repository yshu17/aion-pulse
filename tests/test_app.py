from watcher.app import split_keywords


def test_split_keywords():
    assert split_keywords(" хил,  ММК ,,чант , ") == ["хил", "ММК", "чант"]
    assert split_keywords("") == []


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
        assert len(app.item_vars) == 49
        assert app.item_vars["100000893"].get() is True
        beeps = []
        app.notifier.play = lambda: beeps.append(1)
        app.start()
        with open(log, "ab") as f:
            f.write(line.encode("cp1251"))
        app._tick()
        assert beeps == [1]
        assert "Seller: wts [Клинок Рудры] 5кк" in app.text.get("1.0", "end")

        app.item_vars["100000893"].set(False)
        app._on_items_changed()
        assert json.loads(cfg_path.read_text(encoding="utf-8"))["watch_items"] == []

        app._select_all_items(True)
        assert len(app.cfg.watch_items) == 49
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
        canvas = app.items_canvas
        row = _descendants(canvas).__next__()  # inner frame
        first_item = row.winfo_children()[0]
        wheel = SimpleNamespace(x_root=0, y_root=0, delta=-120)
        # Pretend the pointer is over each widget; no dependence on real screen layout.
        for target in (first_item, row, canvas, app.items_holder):
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
    log.write_bytes((line(300, "Old") + line(90, "Mid") + line(20, "New")).encode("cp1251"))
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(
        json.dumps({"chat_log": str(log), "keywords": ["ммк"], "history_min": 2}), encoding="utf-8"
    )
    root = tk.Tk()
    root.withdraw()
    try:
        app = App(root, cfg_path)
        assert app.history_var.get() == "2 мин"
        beeps = []
        app.notifier.play = lambda: beeps.append(1)
        app.start()
        text = app.text.get("1.0", "end")
        assert "Mid:" in text and "New:" in text and "Old:" not in text
        assert beeps == [1]
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
        assert list(app.groups)[:4] == ["Лата", "Кольчуга", "Кожа", "Ткань"]
        assert "Крылья" in app.groups

        app.group_vars["Лата"].set(True)
        app._on_group_toggled("Лата")
        lata = set(app.groups["Лата"])
        assert len(lata) == 5 and lata <= set(app.cfg.watch_items)
        assert json.loads(cfg_path.read_text(encoding="utf-8"))["watch_items"] == app.cfg.watch_items

        app._toggle_collapsed("Оружие")
        assert app.cfg.collapsed_groups == ["Оружие"]
        assert not app.group_bodies["Оружие"].winfo_manager()
        app._toggle_collapsed("Оружие")
        assert app.cfg.collapsed_groups == []
        assert app.group_bodies["Оружие"].winfo_manager() == "pack"

        app.item_vars[app.groups["Лата"][0]].set(False)
        app._on_items_changed()
        assert app.group_vars["Лата"].get() is False
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
        app.alarm.trigger = lambda entries: alarms.append([m.nick for m, _hits in entries])
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
