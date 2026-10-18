"""Build the portable mob search index from the extracted Aion client TSV files.

The client files are read-only inputs. The generated JSON contains spawn candidates authored
in the client; it does not claim to match the current Aion Empire server exactly.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET


ZONE_MAP_IDS = {
    "dc1": "120010000",
    "df1": "220010000",
    "df1a": "220030000",
    "df2": "220020000",
    "df2a": "220050000",
    "df3": "220040000",
    "df4": "220070000",
    "lf1": "210010000",
    "lf1a": "210030000",
    "lf2": "210020000",
    "lf2a": "210060000",
    "lf3": "210040000",
    "lf4": "210050000",
    "lc1": "110010000",
    "ab1": "400010000",
    "underpass": "600010000",
}

NON_CREATURE_RACES = {"", "barrier", "carrier", "dragon_castle_door", "npc", "teleporter"}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def is_mob(npc: dict[str, str]) -> bool:
    """Keep non-player creatures placed as level spawn points, excluding guards and services."""
    race = npc.get("race_type", "").strip().casefold()
    tribe = npc.get("tribe", "").strip().casefold()
    internal_name = npc.get("internal_name", "").casefold()
    return bool(
        race not in NON_CREATURE_RACES
        and not race.startswith("pc_")
        and not npc.get("function_type", "").strip()
        and tribe != "general"
        and "guard" not in tribe
        and "field_object" not in tribe
        and "summon" not in internal_name
        and "test" not in internal_name
    )


def build_index(source: Path, maps_path: Path) -> dict:
    npcs = read_tsv(source / "client_npcs.tsv")
    by_name: dict[str, dict[str, str]] = {}
    for npc in npcs:
        name = npc.get("internal_name", "").strip()
        if not name:
            continue
        if name in by_name:
            raise ValueError(f"duplicate NPC internal_name in client_npcs.tsv: {name}")
        by_name[name] = npc

    by_id: dict[str, dict[str, str]] = {}
    for npc in npcs:
        npc_id = npc.get("npc_id", "").strip()
        if not npc_id:
            continue
        if npc_id in by_id and by_id[npc_id] != npc:
            raise ValueError(f"duplicate NPC id in client_npcs.tsv: {npc_id}")
        by_id[npc_id] = npc

    maps = json.loads(maps_path.read_text(encoding="utf-8"))
    zones: dict[str, list[dict]] = defaultdict(list)
    catalog: dict[str, dict[str, str]] = {}
    skipped = 0

    def add_point(map_id: str, npc: dict[str, str], gx: float, gy: float, gz: float, point_source: str) -> None:
        nonlocal skipped
        transform = maps.get(map_id)
        if not transform:
            skipped += 1
            return
        image_x = transform["x"][0] * gy + transform["x"][1]
        image_y = transform["y"][0] * gx + transform["y"][1]
        size = float(transform.get("size", 3072))
        if not (0 <= image_x <= size and 0 <= image_y <= size):
            skipped += 1
            return
        label = npc.get("russian_name", "").strip() or npc.get("internal_name", "").strip()
        npc_id = npc.get("npc_id", "").strip()
        if not npc_id:
            skipped += 1
            return
        catalog[npc_id] = {
            "name": label,
            "internal_name": npc.get("internal_name", "").strip(),
        }
        zones[map_id].append({
            "mob_id": npc_id,
            "x": round(image_x, 2),
            "y": round(image_y, 2),
            "gx": round(gx, 2),
            "gy": round(gy, 2),
            "gz": round(gz, 2),
            "source": point_source,
        })

    level_rows = read_tsv(source / "client_level_objects.tsv")
    level_zones: set[str] = set()
    for row in level_rows:
        zone_code = row.get("zone", "").strip()
        map_id = ZONE_MAP_IDS.get(zone_code)
        if row.get("object_type") != "SP" or not map_id:
            continue
        level_zones.add(zone_code)
        npc = by_name.get(row.get("npc_internal_name", ""))
        if not npc or not is_mob(npc):
            skipped += 1
            continue
        try:
            gx, gy, gz = (float(row[f"game_{axis}"].strip()) for axis in ("x", "y", "z"))
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        add_point(map_id, npc, gx, gy, gz, "level")

    # The extracted level tables omit some mapped areas. Use the existing world XML placements
    # for those areas so global search also covers the capital, Abyss and the newer Elyos maps.
    world_dir = source / "raw" / "Data" / "world" / "world"
    for zone_code, map_id in ZONE_MAP_IDS.items():
        if zone_code in level_zones or map_id not in maps:
            continue
        xml_path = world_dir / f"client_world_{zone_code}.txt.xml"
        if not xml_path.is_file():
            xml_path = world_dir / f"client_world_{zone_code}.xml"
        if not xml_path.is_file():
            continue
        try:
            root = ET.parse(xml_path).getroot()
        except (ET.ParseError, OSError):
            continue
        for entry in root.findall(".//npc_info"):
            npc = by_id.get((entry.findtext("nameid") or "").strip())
            pos = entry.find("pos")
            if npc is None or pos is None or not is_mob(npc):
                skipped += 1
                continue
            try:
                gx, gy, gz = (float(pos.findtext(axis) or "") for axis in ("x", "y", "z"))
            except (TypeError, ValueError):
                skipped += 1
                continue
            add_point(map_id, npc, gx, gy, gz, "world")

    for points in zones.values():
        points.sort(key=lambda point: (catalog[point["mob_id"]]["name"].casefold(),
                                       point["mob_id"], point["x"], point["y"]))
    return {
        "version": 1,
        "source": "Aion client client_level_objects.tsv, client_npcs.tsv, client_world_*.xml",
        "source_note": "Координаты — расстановка из клиента; она может отличаться от текущего сервера Aion Empire.",
        "coordinate_note": "x/y — пиксели карты; gx/gy/gz — координаты клиента.",
        "mobs": dict(sorted(catalog.items())),
        "zones": dict(sorted(zones.items())),
        "skipped_rows": skipped,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("client_extract"),
                        help="folder containing the extracted TSV files (read-only)")
    parser.add_argument("--maps", type=Path, default=Path("data/maps/maps.json"))
    parser.add_argument("--output", type=Path, default=Path("local/bestiary/mobs.json"))
    args = parser.parse_args()
    data = build_index(args.source, args.maps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(data['mobs'])} mobs and {sum(map(len, data['zones'].values()))} spawn points "
          f"in {len(data['zones'])} zones to {args.output}")


if __name__ == "__main__":
    main()
