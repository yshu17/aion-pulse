"""SN-5: notification settings from config.json applied to the center and the toast window (no Tk in the core)."""

import json
from types import SimpleNamespace

from watcher.config import Config, read_config
from core.notify.notify_center import NotificationCenter
from core.notify.notify_settings import SOURCES, apply


def test_defaults_show_every_source_with_sound():
    cfg = Config()
    assert (cfg.notify_off, cfg.notify_mute, cfg.notify_dnd) == ([], [], False)
    assert (cfg.notify_corner, cfg.notify_duration, cfg.notify_stack) == ("bottom", 8, 3)
    assert [key for key, _label in SOURCES] == ["chat", "status", "schedule"]


def test_apply_sets_source_rules_and_do_not_disturb():
    center = NotificationCenter(sound=lambda _e: None)
    cfg = Config(notify_off=["schedule"], notify_mute=["chat"], notify_dnd=True)
    apply(cfg, center)
    assert center.rules["schedule"].enabled is False
    assert center.rules["chat"].enabled is True and center.rules["chat"].sound is False
    assert center.rules["status"].sound is True
    assert center.do_not_disturb is True


def test_muted_source_still_shows_but_stays_silent():
    sounds = []
    center = NotificationCenter(sound=sounds.append)
    apply(Config(notify_mute=["chat"]), center)
    assert center.notify("chat", "chat", "Найдено") is not None
    assert sounds == []


def test_apply_sets_the_toast_window_and_repairs_odd_values():
    center = NotificationCenter(sound=lambda _e: None)
    manager = SimpleNamespace(duration=8.0, max_visible=3, corner="bottom")
    apply(Config(notify_corner="top", notify_duration=15, notify_stack=1), center, manager)
    assert (manager.corner, manager.duration, manager.max_visible) == ("top", 15, 1)
    apply(Config(notify_corner="left", notify_duration=3, notify_stack=9), center, manager)
    assert (manager.corner, manager.duration, manager.max_visible) == ("bottom", 8, 3)


def test_settings_survive_config_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"notify_off": ["chat"], "notify_dnd": True, "notify_stack": 2}), encoding="utf-8")
    cfg, notice = read_config(path)
    assert notice == "" and cfg.notify_off == ["chat"] and cfg.notify_dnd and cfg.notify_stack == 2
