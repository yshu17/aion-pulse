# Pulse data formats

The core reads these files. It never computes their paths: the caller passes the folder (`data.open`) or the file.
A missing or broken file gives empty data, never a crash. Text files are UTF-8.

## Bundled with the program (`data/`)

| File | Format | Read by |
|---|---|---|
| `item_names.tsv` | `id<TAB>name` per line; ids are digits | `core.items.catalog.load_item_names` |
| `map_names.tsv` | `map id<TAB>zone name` (official Russian names) | `load_link_names` |
| `quest_names.tsv` | `quest id<TAB>quest name` | `load_link_names` |
| `watch_items.csv` | CSV with a header: `id,name,level,category,grade,icon,kind`; `category` is a section («Лата», «Оружие»…), `grade` is `finality`/`mythic`/`epic`/`unique`/`legend`/`rare`/`common`, `kind` a finer type («Меч») | `load_watch_items` |
| `item_specs.json.gz` | gzip JSON `{item id: spec}`; a spec is `{name, grade, blocks}`, block kinds `pairs`, `props`, `warning`, `hr`, `grid`, `text`, `stones`, `set` (see `core/items/specs.py`); a value may be a JSON string, parsed on first use | `load_specs` |
| `recipes.json.gz` | gzip JSON `{"schema": 1, "recipes": [{product, product_id, count, skill, level, ingredients: [[name, count]]}]}` (not shipped yet) | `load_recipes` |
| `schedule.json` | `{"events": [{day, start, end, name, group, color, kind, maps}], "image", "image_etag", "image_modified", …}`; `day` is `mon`…`sun`, times `HH:MM` in MSK, `end` may be `24:00` or before `start` (next day); `maps` = `{side: map id}` for «на карте»; `image*` is the fingerprint of the KB picture the grid was typed from | `core.schedule.timing.load_events`, `schedule_update.known_fingerprint` |
| `maps/maps.json` | `{map id: {file, size, x: [a, b], y: [a, b], side, layers: [{id, name, file}]}}`; image px = `x[0] * game_y + x[1]`, `y[0] * game_x + y[1]`; `side` is `dark`, `light` or absent | `core.map.zones.load_zones` |
| `maps/labels.tsv` | `map id<TAB>level<TAB>game x<TAB>game y<TAB>text[<TAB>Abyss layer]`; `level` is `main` (whole map) or `zoom` (closer in); `\|` in a name is a line break; `#` starts a comment | `load_labels`, `load_label_layers` |
| `maps/poi.json` | `{"types": {type: {group, name, icon}}, "zones": {map id: [{t, x, y, gx, gy, name, note, side, layer}]}}`; `gx`, `gy` game coordinates (1 unit ≈ 1 m); `x`, `y` are replaced by picture px on load | `core.map.poi.PoiStore.load` |
| `maps/client/*.jpg` | zone pictures, 3072 px | the window only |
| `icons/`, `ui/` | item icons and window graphics | the window only |

## Game data (`data/game/`, built by `tools/build_game_data.py`)

A folder of sections; a screen loads only the sections it shows. IDs are client IDs as strings, links between sections are IDs
only, an unknown value is `null`, a missing record means «not checked». Every section file is `{"schema": 1, "section": name, ...}`;
`.json.gz` files are gzip without a time stamp, so the same tables give the same bytes. Read by `core.game_data.store.GameData`.

| File | Content |
|---|---|
| `manifest.json` | `{schema, built, client_build, sections: {name: {file, records, sha256}}}` |
| `report.json` | counts, missing input tables, links to IDs that do not exist (a count and the first ten) |
| `items.json.gz` | `records`: `id, name, type, weapon, armor, level, price, icon, category, grade, source [, name_source]` (`name_source: "legacy"` = the name is from the older `item_names.tsv`) |
| `recipes.json.gz` | `records`: `id, name, product, count, profession, level, race, ingredients [[item, count]], combo [item] or null, source` |
| `npcs.json.gz` | `records`: `id, name, function, ui, tribe, race, source` |
| `maps.json`, `labels.json.gz` | maps (`id, name, file, size, side`); area labels as `columns` + `rows` |
| `npc_points.json.gz` | `columns [map, npc, x, y, z, zone]`, `rows`: where an NPC stands (game coordinates) |
| `vendors.json.gz` | `columns [npc, item, price, currency, limit, kind]`, `rows`; price and currency are `null` (the client has none) |
| `quests.json.gz` | `records`: `id, name, min_level, max_level, race, category, repeatable, giver, ender, rewards [{type, group, item, amount}]`; `ender` is unknown for all |
| `skills.json.gz` | `skills` (`id, name, classes, level, kind, mp, cooldown_ms, cast_ms, range, requires`) and `learns` (`id, skill, class, race, level, stigma`) |
| `stigmas.json`, `classes.json` | stigma rules (slot unlock levels unknown); class × race with `base_stats` / `per_level` = `null` until the client table is found |
| `drops.sqlite` | `drops(npc_id, item_id, chance_min, chance_max, count_min, count_max)` key `(npc_id, item_id)` plus an index by item; chances and counts are `NULL`; not in git (47 MB), `PRAGMA user_version` 1 |

## Next to the program (user files)

| File | Format | Read by |
|---|---|---|
| `config.json` | one object, the fields of `core.settings.config.Config` (names and defaults there); a wrong type takes its default; a broken file is kept as `config.json.broken-<time>` | `read_config` / `save_config` |
| `schedule_custom.json` | `{"added": [event], "removed": ["day|start|name"]}`; own events get kind «Свои» | `core.schedule.schedule_custom.Custom` |
| `schedule_leads.json` | `{"<day>\|<start>\|<name>": minutes}`: how many minutes before the start the reminder of a belled event comes, when it is not the common `remind_min` (Pulse+) | the launcher (`launcher/src/ui/schedule/useSchedule.ts`) |
| `schedule_source.json` | `{"url": "https://…", "known": "<fingerprint>"}`: the link the schedule is checked by (the KB article by default; a page with the picture or the picture itself, https to a public site) and the state of it that counts as the schedule in use (Pulse+) | the launcher (`launcher/src/ui/schedule/source.ts`) |
| `Chat.log` | the game's chat log (`g_chatlog = "1"` in `system.cfg`): `YYYY.MM.DD HH:MM:SS : text`, CP1251 or UTF-8 | `core.chat.tailer.LogTailer`, `core.chat.session.LogFeed` |

## Local, not in the repository

| File | Format | Read by |
|---|---|---|
| `local/bestiary/npcs.sqlite` | SQLite, `PRAGMA user_version` 1…7, built by `tools/build_bestiary_index.py` from client data and KB profiles; details are zlib-packed JSON with a shared dictionary | `core.bestiary.bestiary_store.BestiaryStore` |
