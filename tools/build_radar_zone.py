"""Use the client's radar picture as a zone's map (dev tool, needs client_extract/ and Pillow).

The radar picture of a zone covers its whole world at one pixel per game metre, and the client's NPC positions sit
exactly on its buildings (image x = game y, image y = game x). Some zones' «newmap» pictures do not: Elysium's
shows the city laid out differently and leaves the market and the port off the map. For such a zone this crops the
radar picture to a square around everything the zone has (points and area names, with a margin) and installs it:

    python tools/build_radar_zone.py lc1 110010000 [margin]     -> data/maps/client/lc1_radar.jpg + maps.json entry

"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MAPS = ROOT / "data" / "maps"


def frame(points: list[tuple[float, float]], margin: float, world: int) -> tuple[int, int, int]:
    """(left, top, side) in radar pixels: a square around the points (game y -> x, game x -> y) inside the world."""
    xs, ys = [gy for _gx, gy in points], [gx for gx, _gy in points]
    side = int(max(max(xs) - min(xs), max(ys) - min(ys)) + 2 * margin)
    side = min(side, world)
    left = int((min(xs) + max(xs)) / 2 - side / 2)
    top = int((min(ys) + max(ys)) / 2 - side / 2)
    left, top = max(0, min(left, world - side)), max(0, min(top, world - side))
    return left, top, side


def zone_points(map_id: str) -> list[tuple[float, float]]:
    """Game (x, y) of the zone's points and area names."""
    poi = json.loads((MAPS / "poi.json").read_text(encoding="utf-8"))["zones"].get(map_id, [])
    points = [(p["gx"], p["gy"]) for p in poi]
    for line in (MAPS / "labels.tsv").read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if not line.startswith("#") and len(parts) >= 5 and parts[0] == map_id:
            points.append((float(parts[2]), float(parts[3])))
    return points


def install(code: str, map_id: str, radar: Path, points: list[tuple[float, float]], margin: float = 160.0) -> dict:
    with Image.open(radar) as image:
        picture = image.convert("RGB")
    world = picture.width  # one pixel per metre
    left, top, side = frame(points, margin, world)
    picture.crop((left, top, left + side, top + side)).save(MAPS / "client" / f"{code}_radar.jpg", quality=88)
    entry = {"file": f"client/{code}_radar.jpg", "size": side, "x": [1.0, float(-left)], "y": [1.0, float(-top)]}
    index_path = MAPS / "maps.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index[map_id] = entry
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return entry


def main() -> int:
    code, map_id = sys.argv[1], sys.argv[2]
    margin = float(sys.argv[3]) if len(sys.argv) > 3 else 160.0
    points = zone_points(map_id)
    entry = install(code, map_id, ROOT / "client_extract" / "radar" / f"{code}.jpg", points, margin)
    print(f"{code} ({map_id}): {len(points)} points, map {entry['size']} px, frame x {entry['x']} y {entry['y']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
