"""Stitch the game's own zone maps (textures/ui/newmap) and print their map transforms.

Input: client_extract/raw/textures/ui/newmap/<zone>/<zone>/<zone>_000..008.png — nine 1024 px tiles in
column-major order (tile i goes to column i // 3, row i % 3), extracted by Codex (client_extract/raw/REPORT.md);
client_extract/raw/Data/world/world/zonemap.xml — the framing of each map.
Output: client_extract/newmap/<zone>.jpg (3072 px). With --install, the zones listed in data/maps/maps.json
are also written to data/maps/client/<zone>.jpg and their maps.json entries point there with the zonemap.xml
transform.

The framing rule (zonemap.xml): the 3072 px picture covers map_width x map_height game metres starting at
offset_x / offset_y; without an offset it covers the whole world (world_width x world_height). The image's
horizontal axis is game y:
    image_x = (game_y - offset_x) * 3072 / map_width,   image_y = (game_x - offset_y) * 3072 / map_height
Dev tool (needs Pillow). Usage: python tools/build_newmaps.py [--install] [zone ...]
"""

import json
import re
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "client_extract" / "raw"
NEWMAP = RAW / "textures" / "ui" / "newmap"
OUT = ROOT / "client_extract" / "newmap"
TILE = 1024
SIZE = 3 * TILE


def zonemaps(path: Path = RAW / "Data" / "world" / "world" / "zonemap.xml") -> dict[str, dict]:
    """zonemap.xml -> {zone code (lower case): {"id", "world", "offset", "map"}}."""
    text = path.read_bytes().decode("utf-16")
    out = {}
    for block in re.findall(r"<zonemap>(.*?)</zonemap>", text, re.S):
        field = dict(re.findall(r"<(\w+)>([^<]*)</\1>", block))
        world = (float(field["world_width"]), float(field["world_height"]))
        offset = (float(field.get("offset_x", 0)), float(field.get("offset_y", 0)))
        size = (float(field.get("map_width", world[0])), float(field.get("map_height", world[1])))
        out[field["name"].lower()] = {"id": field["id"], "world": world, "offset": offset, "map": size}
    return out


def transform(info: dict, image_size: int = SIZE) -> dict:
    """maps.json transform: image_x = x[0] * game_y + x[1], image_y = y[0] * game_x + y[1]."""
    kx, ky = image_size / info["map"][0], image_size / info["map"][1]
    return {"x": [round(kx, 6), round(-info["offset"][0] * kx, 3)], "y": [round(ky, 6), round(-info["offset"][1] * ky, 3)]}


def stitch(zone: str) -> Image.Image | None:
    folder = NEWMAP / zone / zone
    tiles = [folder / f"{zone}_{i:03d}.png" for i in range(9)]
    if not all(t.is_file() for t in tiles):
        return None
    image = Image.new("RGB", (SIZE, SIZE))
    for i, tile in enumerate(tiles):
        with Image.open(tile) as t:
            image.paste(t.convert("RGB"), ((i // 3) * TILE, (i % 3) * TILE))
    return image


def main() -> int:
    install = "--install" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--install"]
    frames = zonemaps()
    zones = args or sorted(p.name for p in NEWMAP.iterdir() if (p / p.name).is_dir())
    index_path = ROOT / "data" / "maps" / "maps.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    for zone in zones:
        image = stitch(zone)
        if image is None:
            print(f"{zone}: no 3x3 tiles")
            continue
        image.save(OUT / f"{zone}.jpg", quality=88)
        info = frames.get(zone)
        print(f"{zone}: {OUT / (zone + '.jpg')}", json.dumps({"id": info["id"], **transform(info)}) if info else "no zonemap")
        if install and info and info["id"] in index:
            image.save(ROOT / "data" / "maps" / "client" / f"{zone}.jpg", quality=85)
            index[info["id"]] = {"file": f"client/{zone}.jpg", "size": SIZE, **transform(info)}
    if install:
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
