# Pulse core

Portable logic of Pulse (ADR-001): no Tk, no Windows API, standard library only. The desktop program in `watcher/`
is one user of it; the launcher (Tauri 2) is the next one. It can run the core as a separate process
(`python -m core`, JSON over stdin / stdout, see [API.md](API.md)) or rewrite it with the same contracts.

Rules (checked by `tests/test_core_boundary.py`):

- imports: the standard library and `core.*` only — never `watcher`, `tkinter`, `PIL`, `ctypes`, `winsound`, `winreg`;
- no paths computed inside: files, names and settings come in as parameters;
- no program timers: the caller ticks (`NotificationCenter.tick`, `LogFeed.poll`, `ReminderPlanner.due`);
  `search_worker` owns one worker thread and is closed by the caller;
- the folder works on its own: the boundary test copies `core/` alone into an empty folder, imports every module and
  answers a `core.version` request through `python -m core`.

| Group | Modules | What it does |
|---|---|---|
| `chat` | tailer, parser, matcher, series, alerts, categories, session, segments, status | read Chat.log, parse links, match keywords and watched items, repeat series, pending alerts, «Весь чат» categories, how a message is drawn, status texts; `session` is the whole watching flow |
| `notify` | notify_center, alert_bridge, notify_settings, notices | notification queue, rules, repeat/snooze, alert ↔ notification link, which notice to raise and what its buttons mean |
| `schedule` | reminders, schedule_view, schedule_custom, schedule_update, timing, reminder_flow | events, day/week views, own events (JSON), KB change check, MSK time helpers, reminders and missed events |
| `bestiary` | bestiary_labels, bestiary_classify, bestiary_store, search_worker, card | SQLite NPC index, categories, hygiene, background search, NPC card texts |
| `map` | poi, zones | map points (load, filter, search, nearest, clustering), zones with coordinates, area names, filter groups |
| `items` | catalog, browser, specs, recipes | item catalog and watch list, the «Что искать» state (sections, filters, search), tooltips, recipes |
| `settings` | config | the settings model, validation, reading / writing config.json (path is a parameter) |
| `update` | updater, selfupdate | GitHub release check, verified download (SHA-256) and file swap |
| `telegram` | tgbatch | chat lines packed into Telegram messages within the rate limit |
| `game_data` | tables, layout, sections, build, store | the game data: one build from the client exports into `data/game/` (a file per section + SQLite drops), one reader; `tools/build_game_data.py` runs it |
| — | api, `__main__`, schema, text | one JSON entry point for other programs ([API.md](API.md)), its typed contract ([api.schema.json](api.schema.json), [api.d.ts](api.d.ts)), shared text helpers |

Each module's docstring lists its public functions and data formats.

Use from Python:

```python
from core.chat.session import LogFeed, WatchSession
from core.items.catalog import load_item_names, load_link_names

maps, quests = load_link_names(data_dir)
session = WatchSession(load_item_names(data_dir / "item_names.tsv"), maps, quests, keywords=["wts"])
feed = LogFeed(chat_log_path, history_min=15)
history, lines = feed.poll()
batch = session.process(lines, now=time.monotonic())
```

Data file formats: [DATA.md](DATA.md). Standalone build: `build_core.bat` -> `pulse-core.exe`.

Version: `core.__version__` (the API contract). The program finds its data folder with `watcher.paths.resource_root()`;
a launcher passes its own.
