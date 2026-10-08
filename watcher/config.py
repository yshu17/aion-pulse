"""config.json next to the exe (or the project folder when run from source)."""

import json
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

DEFAULT_GAME_DIR = r"C:\aMain\Games\AION Imperia\Aion Empire"


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


@dataclass
class Config:
    game_dir: str = DEFAULT_GAME_DIR
    chat_log: str = ""
    keywords: list[str] = field(default_factory=list)
    watch_items: list[str] = field(default_factory=list)
    history_min: int = 0
    collapsed_groups: list[str] = field(default_factory=list)
    poll_interval_ms: int = 500
    cooldown_sec: float = 60
    sound_path: str = ""
    alert_mode: str = "standard"  # "standard" | "nag"
    search_mode: str = "or"  # "or" word or item, "words", "items", "and" word and item
    react_sec: int = 30  # nag mode: unaccepted alerts become «missed» after this; 0 = never
    nag_popup: bool = False  # nag mode: also show the always-on-top popup
    show_counters: bool = True
    chat_minutes: int = 15  # «Весь чат» tab: history shown on open
    chat_system: bool = False  # «Весь чат» tab: include system messages

    def chat_log_path(self) -> Path:
        if self.chat_log:
            return Path(self.chat_log)
        return Path(self.game_dir) / "classic" / "Chat.log"


def save_config(path: Path, cfg: Config) -> None:
    path.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")


def load_config(path: Path) -> Config:
    """Load config; a missing or broken file is replaced with defaults."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config root is not an object")
    except (OSError, ValueError):
        cfg = Config()
        save_config(path, cfg)
        return cfg
    names = {f.name for f in fields(Config)}
    return Config(**{k: v for k, v in data.items() if k in names})
