import json
from pathlib import Path

import pytest

from watcher.config import DEFAULT_GAME_DIR, Config, load_config, save_config


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
