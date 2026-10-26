"""The settings model of Pulse and reading / writing config.json (the path is a parameter).

Portable core: no path of its own. A value of the wrong type falls back to its default, a broken file
is kept as config.json.broken-<time>. `watcher.paths.app_root()` says where the file lives."""

import json
import os
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path

DEFAULT_GAME_DIR = r"C:\aMain\Games\AION Imperia\Aion Empire"


# ui:40: the always-on-top popup is temporarily off. The setting stays in config.json and shows as disabled in the UI.
OVERLAY_POPUP_ENABLED = False


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
    sound_volume: int = 80  # 0..100 %, volume of this program's alert sounds
    alert_mode: str = "standard"  # "standard" | "nag"
    search_mode: str = "or"  # "or" word or item, "words", "items", "and" word and item
    react_sec: int = 30  # nag mode: unaccepted alerts become «missed» after this; 0 = never
    remind_min: int = 5  # SN-8: remind this many minutes before a belled schedule event (5, 15, 30 or 60)
    remind_events: list[str] = field(default_factory=list)  # SN-8: «day|start|name» of the belled events
    remind_last_check: str = ""  # SN-8: MSK time of the last reminder check, to report events missed while closed
    nag_popup: bool = False  # nag mode: also show the always-on-top popup
    show_counters: bool = True  # unused: counters are always shown (kept so old configs load)
    chat_minutes: int = 15  # unused: «Весь чат» uses history_min (kept so old configs load)
    chat_keep_min: int = 10  # Pulse+: a chat message leaves the feed this many minutes after it was written; 0 = it stays
    chat_system: bool = False  # «Весь чат» tab: include system messages
    filter_grades: list[str] = field(default_factory=list)  # item list: shown grades, [] = all
    filter_level_min: int = 0  # item list: lowest level shown, 0 = any
    filter_level_max: int = 0  # item list: highest level shown, 0 = any
    items_width: int = 0  # «Поиск» tab: width of the item list (divider position), 0 = natural
    map_quests: bool = True  # «Карта»: NPCs with quests are shown (kept in step with the «Задания» entry of «Метки»)
    # «Карта», menu «Метки»: kinds of points switched off. The rifts were never drawn before: off until asked for
    map_hidden: list[str] = field(default_factory=lambda: ["rifts"])
    settings_open: bool = False  # first launch leaves the 600 px content usable; saved choices still load
    map_side: str = "dark"  # «Карта»: whose fortress NPCs and quest givers are shown, "dark" / "light"
    game_check: bool = True  # stop watching (and warn) when the game process aion.bin is not running
    filter_type: str = ""  # item list: category («Лата») or «Оружие: Меч», "" = all
    reduce_motion: bool = False  # disable decorative UI animations
    notify_off: list[str] = field(default_factory=list)  # SN-5: notification sources not shown (chat, status, schedule)
    notify_mute: list[str] = field(default_factory=list)  # SN-5: sources shown without sound
    notify_dnd: bool = False  # SN-5: «не беспокоить» — nothing pops up
    notify_corner: str = "bottom"  # SN-5: toasts at the right, "bottom" or "top"
    notify_duration: int = 8  # SN-5: seconds a toast stays (5, 8 or 15)
    notify_stack: int = 3  # SN-5: toasts shown at once (1..3)
    schedule_hidden: list[str] = field(default_factory=list)  # SN-7: kinds of events hidden in the «Расписание» tab
    schedule_check: bool = True  # SN-9: check the knowledge base for a new schedule picture at start
    schedule_seen: str = ""  # SN-9: the site version the user already acknowledged («Понятно»)
    update_check: bool = True  # check GitHub for a newer release at start
    update_seen: str = ""  # the release tag the user already acknowledged («Понятно»)

    def chat_log_path(self) -> Path:
        if self.chat_log:
            return Path(self.chat_log)
        return Path(self.game_dir) / "classic" / "Chat.log"


def save_config(path: Path, cfg: Config) -> None:
    """Write through a temporary file, so an interrupted write never leaves half a JSON file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(asdict(cfg), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _valid(value: object, default: object) -> bool:
    """True when a JSON value has the type of the field's default (bool is not a number here)."""
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    return isinstance(value, str)


def read_config(path: Path) -> tuple[Config, str]:
    """Load config and say what was repaired (empty string when nothing was).

    A broken file is kept as config.json.broken-<time> before defaults are written.
    A field of the wrong type takes its default; the other fields are kept.
    """
    notice = ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config root is not an object")
    except FileNotFoundError:
        cfg = Config()
        save_config(path, cfg)
        return cfg, ""
    except (OSError, ValueError):
        backup = path.with_name(f"{path.name}.broken-{datetime.now():%Y%m%d-%H%M%S}")
        if path.exists():
            os.replace(path, backup)
        cfg = Config()
        save_config(path, cfg)
        return cfg, f"config.json был повреждён, сохранён как {backup.name}; загружены настройки по умолчанию"
    defaults = Config()
    names = {f.name for f in fields(Config)}
    kept = {}
    wrong = []
    for key, value in data.items():
        if key not in names:
            continue
        default = getattr(defaults, key)
        if _valid(value, default):
            kept[key] = value
        else:
            wrong.append(key)
    if wrong:
        notice = "в config.json неверный тип у настроек: " + ", ".join(sorted(wrong)) + "; взяты значения по умолчанию"
    return Config(**kept), notice


def load_config(path: Path) -> Config:
    """Load config; a missing or broken file is replaced with defaults."""
    return read_config(path)[0]
