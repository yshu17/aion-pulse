import json
from pathlib import Path

from watcher.config import DEFAULT_GAME_DIR, Config, load_config, save_config


def test_missing_file_gives_defaults_and_creates_it(tmp_path):
    path = tmp_path / "config.json"
    cfg = load_config(path)
    assert cfg == Config()
    assert cfg.game_dir == DEFAULT_GAME_DIR
    assert json.loads(path.read_text(encoding="utf-8"))["poll_interval_ms"] == 500


def test_broken_json_gives_defaults_and_rewrites(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_config(path) == Config()
    assert json.loads(path.read_text(encoding="utf-8"))["keywords"] == []


def test_non_object_json_gives_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[1, 2]", encoding="utf-8")
    assert load_config(path) == Config()


def test_roundtrip_keeps_cyrillic(tmp_path):
    path = tmp_path / "config.json"
    cfg = Config(keywords=["хил", "ММК"], cooldown_sec=30)
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
