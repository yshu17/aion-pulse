# Map tab: points of interest with filters — design

Status: design agreed in chat on 2026-10-09; waiting for the user's go-ahead to implement.
Interactive version of this plan: `docs/map-poi-plan.html`.

## Goal

Turn the «Карта» tab into an interactive map like aiondb.ru/maps, but nicer and handier:
functional NPCs, teleports, fortresses, artifacts, dungeon entrances, gathering and quests on the
zone maps, each layer behind a filter.

## Decisions

| Topic | Decision |
|---|---|
| Data source | aiondb.ru (Aion Classic), collected once through the user's Chrome. The site blocks scripts, so a plain HTTP crawler can't read it. |
| Version risk | aiondb is «Classic 5.5»; a few NPCs may not exist on the 2.0 server. Every type can be hidden by a filter; wrong points can be removed from the data file. |
| Layers | All four: functional NPCs (10 types), landmarks (fortresses, artifacts, dungeon entrances, Silentera tunnel entrances), gathering (11 types), quests (4 types, level filter). Plus the existing «places from the chat». |
| Icons | Game-style icons taken from aiondb (they are the game's own map icons). Each type also gets a colour so it reads at small sizes. |
| Improvements over the site | Search on the map; «nearby» for a selected point (nearest teleporter, kisk/obelisk, warehouse, dungeon entrance, with distance in metres); clustering of close points when zoomed out; filter presets («Город», «ПвП», «Сбор», «Задания») and remembered filter state. |
| Zones | The 9 zones that already have maps. Pandaemonium: aiondb shows a later city layout, so its points are checked separately and its layers are switched off if they don't line up. |

## Layout

- Left: filter panel — search field, preset chips, layer groups with checkboxes and point counts.
- Centre: the map (existing MapView: wheel zoom to cursor, drag, area names) with icons and clusters;
  game coordinates under the cursor in a corner.
- Right: card of the selected point — name, chat message if it came from the chat, «Рядом» list.

## Components

| Unit | Purpose | Depends on |
|---|---|---|
| `tools/fetch_poi.py` + a Chrome extraction script | One-off collection: per zone and layer, read the svg markers (`a.map-npc-item`, `circle.map-ui-icon`, gathering and quest markers) → `data/maps/poi.json`; download icons → `data/maps/icons/`. | aiondb pages, Chrome |
| `watcher/poi.py` | Pure data: load `poi.json`, types and groups, filter, text search, nearest-of-type, clustering for a zoom level. No Tk. | `poi.json` |
| `watcher/mapview.py` | Drawing: filter panel, icons, clusters, selected-point card, search box; reuses the zoom/pan code. | `poi.py`, PIL |
| `watcher/config.py` | `map_layers` (enabled types), `map_preset`. | — |

### poi.json

```
{"version": 1,
 "types": {"teleport": {"group": "npc", "name": "Привратник", "icon": "teleport.png", "color": "#7F77DD"}, …},
 "zones": {"220070000": [{"t": "teleport", "x": 1901.1, "y": 1260.4, "name": "Рандрис", "npc": 799260,
                          "lvl": null}, …]}}
```
Coordinates are pixels of `data/maps/<zone>.jpg` (aiondb svg × image size / viewBox — already verified for
area names). Distances: convert back to game units with the zone transform (1 game unit ≈ 1 m).

## Error handling

- Missing or broken `poi.json` → the map works as now, the filter panel says «нет данных».
- Unknown type in the data → shown as a generic marker under «Прочее».
- Icon file missing → coloured dot.

## Testing

- `poi.py`: filter by types, search (case/«ё»), nearest with distance, clustering merges points closer
  than N screen px and splits on zoom-in, broken JSON.
- `mapview.py`: toggling a layer adds/removes canvas items; preset sets the right layers; clicking a
  point fills the card; «Рядом» lists the nearest teleporter.
- Data check (manual, with screenshots): points on buildings/roads for each zone.

## Work steps

1. Collect landmarks + functional NPCs for 9 zones; verify placement on the maps.
2. `poi.py` with tests.
3. Filter panel, icons, presets, remembered state.
4. Point card and «Рядом»; chat place links show nearest teleporter / kisk / warehouse.
5. Gathering and quests (collect, layers, quest level filter, clustering for dense layers).
6. Map search, visual polish, README, exe rebuild.
