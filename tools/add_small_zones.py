"""Add the temples and sacred arenas of both capitals to the map (dev tool, needs client_extract/ and Pillow).

Храм Маркутана (dc2), Храм Кайсинель (lc2), Священная арена Маркутана (arena_d_lobby), Священная арена Кайсинель
(arena_l_lobby). The client has no game map («newmap») for them, only the small radar picture of the area: 128 px
tiles, two or three to a side, laid out column by column. It is stitched, padded to a square and enlarged four
times.

Framing (radar pixels per game metre and the game position of the picture's corner):
- the arenas: zonemap.xml gives it (offset_x / offset_y, map_width); 26 of 38 NPCs of Kaisinel's arena and 23 of 38
  of Marchutan's stand on a building drawn on the picture, the rest in the yards around them;
- the temples: zonemap.xml has none (world size 0). Fitted here so that all 13 NPCs of each temple stand on the
  temple drawn on the picture: approximate, a few metres either way.

Points: the NPCs placed in each zone's client world XML, typed by their function as on the other maps
(tools/build_poi.py), and the arena gates as entrances.

    python tools/add_small_zones.py      writes data/maps/client/<code>.jpg, maps.json entries, their poi.json points
"""

from __future__ import annotations

import csv
import glob
import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "client_extract" / "raw"
MAPS = ROOT / "data" / "maps"
TILE, ENLARGE = 128, 4
SAME_SPOT_M = 1.0
FUNCTIONS = {"teleport": "teleport", "warehouse": "warehouse", "merchant": "merchant", "coin_merchant": "coin_merchant",
             "vendor": "vendor", "stigma_master": "stigma", "postbox": "postbox", "bindstone": "bindstone"}
# code: (map id, radar tile folder, columns, rows, radar px per metre, game y and game x of the picture's corner)
ZONES = {
    "dc2": ("120020000", "pak_069/dc2/radarmap_area_dc2_a", 2, 2, 0.8, 1291.0, 1421.0),
    "lc2": ("110020000", "pak_076/lc2/radarmap_area_lc2_a", 2, 2, 0.9, 1480.0, 2045.0),
    "arena_d_lobby": ("120080000", "pak_083/arena_d_lobby/radarmap_area_arena_d_lobby", 2, 2, 256 / 190, 180.0, 434.0),
    "arena_l_lobby": ("110070000", "pak_083/arena_l_lobby/radarmap_area_arena_l_lobby", 2, 3, 256 / 218, 160.0, 413.0),
}


def stitch(folder: str, columns: int, rows: int) -> Image.Image:
    tiles = sorted(glob.glob(str(RAW / "textures" / "ui" / "zonemap" / folder / "*.png")))
    side = max(columns, rows) * TILE
    picture = Image.new("RGB", (side, side))
    for index, tile in enumerate(tiles[: columns * rows]):
        with Image.open(tile) as image:
            picture.paste(image.convert("RGB"), ((index // rows) * TILE, (index % rows) * TILE))
    return picture.resize((side * ENLARGE, side * ENLARGE), Image.LANCZOS)


def world_npcs(code: str) -> list[tuple[str, float, float]]:
    text = (RAW / "Data" / "world" / "world" / f"client_world_{code}.txt.xml").read_bytes().decode("utf-8", "replace")
    return [(nid, float(x), float(y)) for nid, x, y in
            re.findall(r"<npc_info>.*?<nameid>(\d+)</nameid>.*?<x>([\d.]+)</x>\s*<y>([\d.]+)</y>", text, re.S)]


def points(code: str, to_image, npcs: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    for nid, gx, gy in world_npcs(code):
        npc = npcs.get(nid, {})
        name = npc.get("russian_name", "").strip()
        kind = FUNCTIONS.get(npc.get("function_type", "").strip().lower())
        if kind is None and re.match(r"(Врата|Вход)\b", name):
            kind = "dungeon"  # the arena gates
        if kind is None or not name:
            continue
        if any(p["name"] == name and abs(p["gx"] - gx) < SAME_SPOT_M and abs(p["gy"] - gy) < SAME_SPOT_M for p in out):
            continue
        x, y = to_image(gx, gy)
        out.append({"t": kind, "x": round(x, 1), "y": round(y, 1), "gx": round(gx, 1), "gy": round(gy, 1), "name": name})
    return out


def main() -> int:
    npcs = {r["npc_id"]: r for r in csv.DictReader(open(ROOT / "client_extract" / "client_npcs.tsv", encoding="utf-8"),
                                                     delimiter="\t")}
    index_path, poi_path = MAPS / "maps.json", MAPS / "poi.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    poi = json.loads(poi_path.read_text(encoding="utf-8"))
    for code, (map_id, folder, columns, rows, per_metre, corner_y, corner_x) in ZONES.items():
        picture = stitch(folder, columns, rows)
        picture.save(MAPS / "client" / f"{code}.jpg", quality=88)
        k = per_metre * ENLARGE  # map pixels per game metre
        index[map_id] = {"file": f"client/{code}.jpg", "size": picture.width,
                         "x": [round(k, 6), round(-corner_y * k, 3)], "y": [round(k, 6), round(-corner_x * k, 3)]}
        made = points(code, lambda gx, gy: (k * gy - corner_y * k, k * gx - corner_x * k), npcs)
        poi["zones"][map_id] = made
        print(f"{code} ({map_id}): map {picture.width} px, {len(made)} points")
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    poi_path.write_text(json.dumps(poi, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
