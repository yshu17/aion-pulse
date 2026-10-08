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
