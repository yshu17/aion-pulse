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
        assert len(app.item_vars) == 48
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
        assert len(app.cfg.watch_items) == 48
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
        for target in (canvas, app.items_holder):
            canvas.yview_moveto(0)
            x = target.winfo_rootx() + 40
            y = target.winfo_rooty() + 40
            app._on_mouse_wheel(SimpleNamespace(x_root=x, y_root=y, delta=-120))
            assert canvas.yview()[0] > 0, target
        canvas.yview_moveto(0)
        text_x = app.text.winfo_rootx() + 20
        text_y = app.text.winfo_rooty() + 20
        app._on_mouse_wheel(SimpleNamespace(x_root=text_x, y_root=text_y, delta=-120))
        assert canvas.yview()[0] == 0
    finally:
        root.destroy()
