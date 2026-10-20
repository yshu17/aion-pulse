import json
from pathlib import Path

import pytest

from core.settings.config import DEFAULT_GAME_DIR, Config, load_config, save_config


@pytest.mark.parametrize("content", [None, "{not json", "[1, 2]"])  # missing, broken, not an object
def test_bad_or_missing_file_gives_defaults_and_rewrites_it(tmp_path, content):
    path = tmp_path / "config.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    cfg = load_config(path)
    assert cfg == Config() and cfg.game_dir == DEFAULT_GAME_DIR and cfg.game_check is True
    assert json.loads(path.read_text(encoding="utf-8"))["poll_interval_ms"] == 500


def test_roundtrip_keeps_cyrillic_and_lists(tmp_path):
    path = tmp_path / "config.json"
    assert Config().watch_items == []
    cfg = Config(keywords=["хил", "ММК"], cooldown_sec=30, watch_items=["100000893", "100001081"])
    save_config(path, cfg)
    assert "хил" in path.read_text(encoding="utf-8")
    assert load_config(path) == cfg


def test_unknown_keys_ignored_missing_keys_default(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"keywords": ["чант"], "extra": 1}), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.keywords == ["чант"]
    assert cfg.poll_interval_ms == 500


def test_chat_log_path_default_and_override():
    assert Config(game_dir=r"D:\Aion").chat_log_path() == Path(r"D:\Aion") / "classic" / "Chat.log"
    assert Config(chat_log=r"E:\x\Chat.log").chat_log_path() == Path(r"E:\x\Chat.log")


def test_broken_file_is_kept_as_backup_and_user_is_told(tmp_path):
    from core.settings.config import read_config

    path = tmp_path / "config.json"
    path.write_text("{not json, но с настройками хил", encoding="utf-8")
    cfg, notice = read_config(path)
    assert cfg == Config()
    backups = list(tmp_path.glob("config.json.broken-*"))
    assert len(backups) == 1 and "хил" in backups[0].read_text(encoding="utf-8")
    assert backups[0].name in notice and "по умолчанию" in notice


def test_wrong_type_takes_default_for_that_field_only(tmp_path):
    from core.settings.config import read_config

    path = tmp_path / "config.json"
    path.write_text(json.dumps({"keywords": None, "cooldown_sec": 45, "nag_popup": "да", "history_min": True}),
                    encoding="utf-8")
    cfg, notice = read_config(path)
    assert cfg.keywords == [] and cfg.nag_popup is False and cfg.history_min == 0
    assert cfg.cooldown_sec == 45  # a valid field is kept
    assert "keywords" in notice and "nag_popup" in notice and "history_min" in notice
    assert "cooldown_sec" not in notice


def test_valid_file_gives_no_notice_and_missing_file_is_created_quietly(tmp_path):
    from core.settings.config import read_config

    path = tmp_path / "config.json"
    assert read_config(path) == (Config(), "") and path.is_file()
    save_config(path, Config(keywords=["хил"]))
    assert read_config(path) == (Config(keywords=["хил"]), "")


def test_save_is_atomic_and_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "config.json"
    save_config(path, Config(keywords=["а"]))
    save_config(path, Config(keywords=["б"]))
    assert load_config(path).keywords == ["б"]
    assert not (tmp_path / "config.json.tmp").exists()


def test_one_folder_build_keeps_settings_outside_its_folder(tmp_path, monkeypatch):
    """A rebuild replaces the build folder: config.json must live next to it, not inside."""
    import sys
    from watcher.paths import app_root
    build = tmp_path / "Pulse-Local"
    (build / "_internal").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(build / "Pulse-Local.exe"))
    assert app_root() == tmp_path
    (build / "_internal").rmdir()  # a one-file exe keeps it next to itself
    assert app_root() == build
