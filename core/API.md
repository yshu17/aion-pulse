# Pulse core API

Version 2.0.0 (`core.__version__`). A major change means a method or its data changed incompatibly.

## How to call

From Python: `CoreApi().call(method, params)` returns plain JSON data.

From another program (the launcher): start `python -m core` once and keep it. Send one JSON request per line to
stdin, read one JSON answer per line from stdout. Text is UTF-8. An empty line stops the process.

```
→ {"id": 1, "method": "data.open", "params": {"data_dir": "C:/Pulse/data"}}
← {"id": 1, "result": {"items": 61234, "watch_items": 27771, "zones": 20, "points": 1924, "events": 60}}
→ {"id": 2, "method": "nope"}
← {"id": 2, "error": {"type": "ValueError", "message": "unknown method: nope"}}
```

An error is an answer, never a crash: the process keeps running.

Conventions:

- `now` of the `session.*` methods is a monotonic clock in seconds that the caller owns.
- Schedule times are MSK wall-clock ISO strings, for example `2026-10-14T20:30:00`. Without `now` the current MSK time is used.
- Dataclasses become objects with the same field names; datetimes become ISO strings.

## Methods

| Method | Params | Result |
|---|---|---|
| `core.version` | — | `{version, methods}` |
| `data.open` | `data_dir` | counts; loads item names, watchable items, map zones, points, schedule |
| `chat.parse` | `line`, `any` (bool) | a «Поиск группы» message `{time, nick, text, raw, item_ids}`; with `any` every channel `{…, channel, color, verb}`; `null` for other lines |
| `session.configure` | any of `keywords`, `watch_items` (ids), `mode` (`or`/`words`/`items`/`and`), `alert_mode` (`standard`/`nag`), `cooldown_sec`, `react_sec` | `{ok}` |
| `session.process` | `lines`, `now` | Batch: `{entries: [{msg, hits, kind, alert_id}], places: [...], announce: [ids]}`; `kind` is `loud`, `quiet` or `history` |
| `session.history` | `lines`, `now` | Batch of matches from before Start (not counted, no alerts) |
| `session.open_log` | `path`, `history_min` | `{ok}`; then `session.poll` reads the file |
| `session.poll` | `now` | `{history: Batch or null, batch: Batch}`; `history` only at the first poll |
| `session.accept` | `alert_id` | `{accepted: [ids]}` (the alert and the rest of its repeat series) |
| `session.accept_all` | — | `{accepted: [ids]}` |
| `session.expire` | `now` | `{missed: [ids]}` (nag alerts older than `react_sec`) |
| `session.state` | `now` | `{found, reacted, missed, pending, remaining: {id: seconds}}` |
| `session.stop` | — | `{ok}`; repeat series start anew, the log is closed |
| `items.list` | `query`, `filter` `{grades, level_min, level_max, type}`, `checked` | `{sections: {name: [ids]}, matches, types, grades}` |
| `map.zones` | — | `[{map_id, name, side, size}]` |
| `map.search` | `map_id`, `query`, `types`, `side`, `layer` | points `[{zone, type, x, y, gx, gy, name, note, side, layer}]`; `x`, `y` are pixels of the zone picture |
| `map.nearest` | `map_id`, `x`, `y` (game), `type` | `{point, metres}` or `null` |
| `schedule.day` | `day` (`mon`…`sun`) | events of that weekday |
| `schedule.next` | `now`, `limit` | `[{event, start, end, until}]` |
| `schedule.reminders` | `belled` (events), `lead_min`, `now` | reminders due now `[{key, title, text, event, start, end}]`, each once per process |
| `schedule.missed` | `belled`, `last`, `now` | `[{event, start}]` missed since `last` (one week at most) |
| `bestiary.open` | `path` (npcs.sqlite) | `{version, coverage}` |
| `bestiary.search` | `text`, `category`, `race`, `rank`, `map_id`, `offset`, `limit`, `min_level`, `max_level`, `region`, `order`, `hide_low` | `{rows, total}` |
| `bestiary.detail` | `npc_id` | the NPC card or `null` |
| `update.check` | `body` (GitHub release JSON), `current` | `{tag, url, newer}` |
| `chat.segments` | `text` (a cleaned message), `hits` | `[{text, kind, hit, item_id, grade, place}]`; `kind` is `text`, `item` or `place` |
| `chat.status_chip` | `text` (status line) | `{short, kind}`; `kind` is `live`, `warn`, `error` or `idle` |
| `chat.empty_feed` | `running`, `mode`, `keywords`, `watch_items` | `{title, hint}` of an empty «Поиск» feed |
| `chat.search_hint` | `mode`, `keywords`, `watch_items` | what the search mode is missing, `""` when nothing |
| `notify.post` | `source`, `kind`, `title`, `text`, `actions` `[[id, label]]`, `sound`, `repeat_after`, `now` | the notification `{id, …}` or `null` (source off) |
| `notify.next` | `now` | notifications to show now (repeats and snoozes that came due included) |
| `notify.acknowledge` | `id` | `{ok}`; stops its repeats |
| `notify.snooze` | `id`, `seconds`, `now` | `{ok}` |
| `notify.settings` | `off`, `mute` (sources), `dnd` | `{ok}` |
| `notify.state` | — | `{queued, unread, dnd, sources}` |
| `notice.release` | `found` `[tag, url]`, `can_install`, `current`, `seen` | `{source, kind, title, text, actions}` or `null` |
| `notice.schedule_check` | `status` (`ok`/`err`), `value`, `known`, `seen`, `manual` | notice or `null` |
| `notice.route` | `action`, `key`, `release_key`, `schedule_key` | what a button means: `open_site`, `install`, `open_release`, `release_seen`, `schedule_seen`, `accept_alerts`, `retry`, `open` |
| `schedule.custom_open` | `path` (schedule_custom.json) | `{events}`; own events join the schedule |
| `schedule.custom_add` | `event` | `{events}` (saved to the file) |
| `schedule.custom_add_days` | `event`, `days` | `{events}` |
| `schedule.custom_edit` | `old`, `new` | `{events}` |
| `schedule.custom_remove` | `event` | `{events}` |
| `schedule.to_text` | `events` | the editable text of events |
| `schedule.parse_text` | `text` | `{events, errors}` |
| `schedule.site_check` | `seen`, `manual` | `{status, value, notice}`; asks the knowledge base (network) |
| `items.spec` | `item_id` | the tooltip `{name, grade, blocks}` with the «made from» block, or `null` |
| `settings.read` | `path` (config.json) | `{config, notice}`; a broken file is set aside, defaults are written |
| `settings.save` | `path`, `values` | `{ok}`; unknown keys are ignored |
| `map.cluster` | `map_id`, `scale`, `dx`, `dy`, `radius`, `types`, `side`, `layer` | icons `[{x, y, type, count, points}]` on screen |
| `bestiary.filters` | — | `{races, ranks, zones}` |
| `bestiary.regions` | `map_id` | region names |
| `bestiary.areas` | `npc_id` | spawn areas `[{map_id, polygon, …}]` |
| `telegram.add` | `lines`, `now` | `{queued}` |
| `telegram.poll` | `now` | `{messages, queued, dropped}`: Telegram messages to send now within the rate limit |

## What stays in the program, not in the core

Windows-only shell: the game process check (`watcher/gamecheck.py`), sounds (`watcher/notifier.py`), toast windows and
window sizing, PyInstaller paths (`watcher/paths.py`). A launcher does these its own way: it calls the core for the
data and decides how to show a notification or play a sound.
