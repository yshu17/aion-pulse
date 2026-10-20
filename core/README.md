# Pulse core

Portable logic of Pulse (ADR-001): no Tk, no Windows API, standard library only. The desktop program in `watcher/`
is one user of it; the launcher (Tauri 2) is the next one — by a Python sidecar process or by a rewrite with the
same contracts.

Rules (checked by `tests/test_core_boundary.py`):

- imports: the standard library and `core.*` only — never `watcher`, `tkinter`, `PIL`, `ctypes`, `winsound`, `winreg`;
- no paths computed inside: files, names and settings come in as parameters;
- no program timers: the caller ticks (`NotificationCenter.tick`, `LogTailer.read_new`);
  `search_worker` owns one worker thread and is closed by the caller;
- the folder works on its own: the boundary test copies `core/` alone into an empty folder and imports every module.

| Group | Modules | What it does |
|---|---|---|
| `chat` | tailer, parser, matcher, series, alerts | read new Chat.log lines, parse links, match watched items, series, pending alerts |
| `notify` | notify_center, alert_bridge, notify_settings | notification queue, rules, repeat/snooze, alert ↔ notification link |
| `schedule` | reminders, schedule_view, schedule_custom, schedule_update | reminders, day/week views, own events (JSON), KB change check |
| `bestiary` | bestiary_labels, bestiary_classify, bestiary_store, search_worker | SQLite NPC index, categories, hygiene, background search |
| `map` | poi | map points: load, filter, search, nearest, clustering |
| `items` | specs, recipes | item tooltips, craft recipes |
| `telegram` | tgbatch | chat lines packed into Telegram messages within the rate limit |

Each module's docstring lists its public functions and data formats.

Use from Python:

```python
from core.chat.parser import parse_line
msg = parse_line(line, item_names, maps=map_names, quests=quest_names)
```

The program loads the bundled names with `watcher.catalog.load_link_names(data_dir)`; a launcher passes its own.
