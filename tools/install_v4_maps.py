"""Install the already extracted v4 client maps into the map tab.

Inputs live in client_extract/; this script never reads or writes the game directory.
It installs only zones with a usable client frame and leaves lc2 (zero-size frame) out.
Usage: python tools/install_v4_maps.py
"""

import csv
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACT = ROOT / "client_extract"
RAW = EXTRACT / "raw"
INDEX = ROOT / "data" / "maps" / "maps.json"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def main() -> int:
    maps = json.loads(INDEX.read_text(encoding="utf-8"))
    frames = {row["zone"]: row for row in rows(RAW / "zone_map_frames.tsv")}
    zone_codes = ("lf1", "lf1a", "lf2", "lf2a", "lf3", "lc1")
    client_dir = ROOT / "data" / "maps" / "client"
    relief_dir = ROOT / "data" / "maps" / "relief"
    client_dir.mkdir(parents=True, exist_ok=True)
    relief_dir.mkdir(parents=True, exist_ok=True)

    for code in zone_codes:
        frame = frames[code]
        width, height = float(frame["map_width"]), float(frame["map_height"])
        if width <= 0 or height <= 0:
            print(f"{code}: skipped; map frame has no dimensions")
            continue
        map_id = frame["map_id"]
        source = EXTRACT / "newmap" / f"{code}.jpg"
        radar = EXTRACT / "radar" / f"{code}.jpg"
        if not source.is_file():
            print(f"{code}: skipped; newmap raster is missing")
            continue
        shutil.copy2(source, client_dir / source.name)
        if radar.is_file():
            shutil.copy2(radar, relief_dir / radar.name)
        kx, ky = 3072 / width, 3072 / height
        maps[map_id] = {
            "file": f"client/{source.name}", "size": 3072,
            "x": [round(kx, 6), round(-float(frame["offset_x"]) * kx, 3)],
            "y": [round(ky, 6), round(-float(frame["offset_y"]) * ky, 3)],
        }
        print(f"{code} ({map_id}): client map and frame installed" + (" with radar" if radar.is_file() else ""))

    abyss = []
    for layer_id in (1, 2, 3):
        source = EXTRACT / "newmap" / f"ab1_{layer_id}.jpg"
        if source.is_file():
            shutil.copy2(source, client_dir / source.name)
            abyss.append({"id": layer_id, "name": f"Слой {layer_id}", "file": f"client/{source.name}"})
    frame = frames["ab1"]
    kx, ky = 3072 / float(frame["map_width"]), 3072 / float(frame["map_height"])
    maps[frame["map_id"]] = {
        "file": abyss[0]["file"] if abyss else "client/ab1_1.jpg", "size": 3072,
        "x": [round(kx, 6), 0], "y": [round(ky, 6), 0], "layers": abyss,
    }
    INDEX.write_text(json.dumps(maps, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ab1 ({frame['map_id']}): {len(abyss)} layers installed; height-to-layer thresholds are not in this index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
