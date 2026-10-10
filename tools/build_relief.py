"""Build the «Рельеф» map theme: the client's radar maps cut to the same frame as the game maps.

Input: client_extract/radar/<zone>.jpg — the radar (minimap) picture of each zone, extracted by Codex; it covers
the whole world (world_width x world_height in zonemap.xml), while the game map (newmap) covers only
map_width x map_height from offset_x / offset_y. client_extract/raw/Data/world/world/zonemap.xml — that framing.
Output: data/maps/relief/<zone>.jpg, 3072 px, for every zone in data/maps/maps.json. The crop is the game map's
frame, so the game map's transform in maps.json fits the relief picture as well: points need no new calibration.
Dev tool (needs Pillow). Usage: python tools/build_relief.py [zone ...]
"""

import json
import sys
from pathlib import Path

from PIL import Image

from build_newmaps import SIZE, zonemaps

ROOT = Path(__file__).resolve().parent.parent
RADAR = ROOT / "client_extract" / "radar"
OUT = ROOT / "data" / "maps" / "relief"


def frame_box(info: dict, radar_size: tuple[int, int]) -> tuple[float, float, float, float]:
    """The game map's frame in radar pixels: (left, top, right, bottom). Horizontal is game y (offset_x)."""
    kx, ky = radar_size[0] / info["world"][0], radar_size[1] / info["world"][1]
    left, top = info["offset"][0] * kx, info["offset"][1] * ky
    return left, top, left + info["map"][0] * kx, top + info["map"][1] * ky


def main() -> int:
    frames = zonemaps()
    index = json.loads((ROOT / "data" / "maps" / "maps.json").read_text(encoding="utf-8"))
    by_code = {Path(info["file"]).stem: map_id for map_id, info in index.items()}
    zones = sys.argv[1:] or sorted(by_code)
    OUT.mkdir(parents=True, exist_ok=True)
    for zone in zones:
        radar = RADAR / f"{zone}.jpg"
        info = frames.get(zone)
        if not radar.is_file() or info is None:
            print(f"{zone}: no radar map or zonemap")
            continue
        with Image.open(radar) as image:
            box = frame_box(info, image.size)
            # Altgard's frame runs past the world's edge: crop() fills the part outside with black
            relief = image.convert("RGB").crop(tuple(round(v) for v in box)).resize((SIZE, SIZE), Image.LANCZOS)
        relief.save(OUT / f"{zone}.jpg", quality=82)
        print(f"{zone}: crop {tuple(round(v) for v in box)} of {image.size} -> {OUT / (zone + '.jpg')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
