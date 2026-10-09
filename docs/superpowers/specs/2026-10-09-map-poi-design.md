# Map tab: points of interest with filters — design (v2, client data)

Status: v2 written 2026-10-09 after Codex extracted the local client data (`CLAUDE_HANDOFF.md`);
waiting for the user's review. Interactive version: `docs/map-poi-plan.html`.

## Goal

Turn the «Карта» tab into an interactive map like aiondb.ru/maps, but nicer and handier:
functional NPCs, portals, fortresses, artifacts, dungeon entrances, gathering and quest points on
the zone maps, each layer behind a filter.

## What changed from v1

| | v1 | v2 |
|---|---|---|
| Points | collected from aiondb.ru through Chrome | taken from the local client (mission XML of 12 zones, already extracted by Codex) |
| Maps | aioncodex tiles, 2048 px | the client's own zone maps, 3072 px (already wired in `maps.json`) |
| Icons | aiondb icons | the client's own map icons (`abyss_fortress`, `abyss_artifact`, `abyss_indun`, `teleport_dest`, …) |
| Gaps | — | the client lacks some server-spawned NPCs (e.g. 2 teleporters in Kelkmaros vs 7 on aiondb) → optional later step: fill gaps from aiondb |

## Data available (9 active zones)

| Layer | Source | Count |
|---|---|---|
| Functional NPCs: Merchant 129, Coin merchant 71, Teleport 35, Vendor (broker) 16, Warehouse 16, Stigma master 5, Postbox 1 | `client_level_objects.tsv` (`function_type`, Russian name) | 273 |
| Portals | `object_type = Portal` | 199 |
| Fortresses / artifacts | `client_level_entities.tsv` (`AbyssArtifacts`, …) + client icons | to be counted per zone |
| Dungeon / direct points | `DP` | 109 |
| Gathering | `HSP`, resource kind from the name (`herb`, `metal`, `berry`, `aether`, …) | 11 294 |
| Quest points | `KP` 596 + `MP` 352 | 948 |
| Monster spawns | `SP` | 38 289 — not shown by default (too dense; maybe later with clustering) |

All rows of the active zones already have `image_x / image_y` in map pixels; the transform was checked
against 712 «Место» links from the user's chat log.

## Decisions

| Topic | Decision |
|---|---|
| Data | Client data first (exact for this client). aiondb only as an optional gap filler later. |
| Repository / exe size | Raw extraction (79 MB: 421 dungeon maps, UI atlases, big TSVs, 3 un-calibrated zones) moves to `client_extract/` — not in `data/`, so not bundled, and not committed. The app ships 9 zone maps + one compact `data/maps/poi.json` (~1 MB) + a few icons. |
| Map size | Keep 3072 px for sharp zoom; exe grows to ~60 MB. Downscaling to 2048 px is a later option. |
| Icons | Only ready-made icons, nothing drawn: the client's own icons first; a missing one (e.g. function-NPC marks if not found in `ui.pak`) comes from aiondb's icon set (also game art). |
| Layers | Functional NPCs (each type separately), portals, fortresses/artifacts, dungeon entrances, gathering (by resource kind), quest points, places from the chat. |
| Improvements | Search on the map; «Рядом» for a selected point with distance in metres; clustering of close points when zoomed out; presets «Город», «ПвП», «Сбор», «Задания»; remembered filter state. |
| Visual design | Use the installed skills `ui-ux-pro-max`, `design-theme-guide`, `high-end-visual-design`; check with `ui-visual-validator` on screenshots. |

## Layout

- Left: filter panel — search, preset chips, layer groups with checkboxes and point counts.
- Centre: the map (existing MapView) with icons and clusters; game coordinates under the cursor.
- Right: card of the selected point — name, role, coordinates, chat message if from the chat, «Рядом».

## Components

| Unit | Purpose |
|---|---|
| `tools/build_poi.py` | client TSVs → `data/maps/poi.json` (types, layers, Russian names, map pixels, gathering kind); copies the needed icons to `data/maps/icons/` |
| `watcher/poi.py` | pure data: load, filter, search, nearest-of-type with metres, clustering per zoom — no Tk, fully tested |
| `watcher/mapview.py` | filter panel, icons, clusters, point card, search box; reuses zoom/pan |
| `watcher/config.py` | `map_layers`, `map_preset` |

## Error handling

Missing/broken `poi.json` → map works as now, panel says «нет данных». Unknown type → generic marker in
«Прочее». Missing icon → the type's ready-made fallback icon from aiondb (never a drawn one).

## Testing

`poi.py`: filters, search («ё»/case), nearest with distance, clustering split/merge, broken JSON.
`mapview.py`: toggling a layer adds/removes items; presets; click fills the card; «Рядом».
Visual: screenshots per zone, checked with `ui-visual-validator`.

## Work steps

0. Tidy up: move raw extraction to `client_extract/` (git-ignored), commit Codex's work, keep the exe lean.
1. `tools/build_poi.py` → `poi.json` + icons; verify on screenshots.
2. `poi.py` with tests.
3. Filter panel, icons, presets, remembered state.
4. Point card and «Рядом»; chat place links show the nearest teleporter / warehouse / portal.
5. Gathering and quest layers with clustering.
6. Optional: fill missing teleporters / kisks from aiondb.
7. Map search, visual polish with the design skills, README, exe rebuild.
