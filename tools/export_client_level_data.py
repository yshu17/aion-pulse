"""Export map-relevant objects from extracted Aion mission XML files.

The XML comes from each zone's ``levels/<zone>/level.pak``. The script keeps
the client's authored coordinates and, where the active map index has a known
transform, adds image-pixel coordinates for direct map overlays.
"""

from __future__ import annotations

import argparse
import csv
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


ZONE_IDS = {
    "dc1": "120010000",
    "df1": "220010000",
    "df1a": "220030000",
    "df2": "220020000",
    "df2a": "220050000",
    "df3": "220040000",
    "df4": "220070000",
    "lf1": "210020000",
    "lf2": "210030000",
    "lf3": "210040000",
    "lf4": "210050000",
    "underpass": "600010000",
}

OBJECT_TYPES = {
    "SP", "HSP", "KP", "MP", "DP", "Portal", "StartPoint", "Location",
    "SeedPoint", "TP", "EP", "BSP", "AP", "CP",
}
ENTITY_CLASSES = {
    "client_npc", "PlaceableObject", "Milestone", "Milestone_Ndist",
    "BasicEntity", "AbyssArtifacts_Effect", "AbyssArtifacts",
}


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def coordinates(raw: str | None) -> tuple[str, str, str]:
    if not raw:
        return "", "", ""
    parts = raw.split(",")
    if len(parts) != 3:
        return "", "", ""
    return tuple(part.strip() for part in parts)  # type: ignore[return-value]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="folder containing <zone>/mission_mission0.xml")
    parser.add_argument("--output", type=Path, default=Path("data/maps/client"))
    args = parser.parse_args()

    npc_rows = load_tsv(args.output / "client_npcs.tsv")
    npcs = {row["internal_name"]: row for row in npc_rows if row.get("internal_name")}
    try:
        map_index = json.loads((args.output.parent / "maps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        map_index = {}

    objects: list[dict[str, object]] = []
    entities: list[dict[str, object]] = []
    object_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()

    for zone in ZONE_IDS:
        mission = args.source / zone / "mission_mission0.xml"
        if not mission.is_file():
            continue
        root = ET.parse(mission).getroot()
        map_id = ZONE_IDS[zone]
        transform = map_index.get(map_id, {})
        x_transform, y_transform = transform.get("x"), transform.get("y")

        for item in root.iter("Object"):
            kind = item.get("Type", "")
            if kind not in OBJECT_TYPES:
                continue
            gx, gy, gz = coordinates(item.get("Pos"))
            if not gx:
                continue
            npc_key = item.get("npc", "")
            npc = npcs.get(npc_key, {})
            ix = float(x_transform[0]) * float(gy) + float(x_transform[1]) if x_transform else ""
            iy = float(y_transform[0]) * float(gx) + float(y_transform[1]) if y_transform else ""
            objects.append({
                "zone": zone, "map_id": map_id, "object_type": kind,
                "object_name": item.get("Name", ""), "npc_internal_name": npc_key,
                "npc_russian_name": npc.get("russian_name", ""),
                "function_type": npc.get("function_type", ""),
                "game_x": gx, "game_y": gy, "game_z": gz,
                "image_x": round(ix, 2) if ix != "" else "",
                "image_y": round(iy, 2) if iy != "" else "",
                "subzone": item.get("subzone", ""), "angles": item.get("Angles", ""),
                "direction": item.get("dir", ""), "idle_range": item.get("iidle_range", ""),
            })
            object_counts[f"{zone}:{kind}"] += 1

        for item in root.iter("Entity"):
            kind = item.get("EntityClass", "")
            if kind not in ENTITY_CLASSES:
                continue
            gx, gy, gz = coordinates(item.get("Pos"))
            if not gx:
                continue
            ix = float(x_transform[0]) * float(gy) + float(x_transform[1]) if x_transform else ""
            iy = float(y_transform[0]) * float(gx) + float(y_transform[1]) if y_transform else ""
            entities.append({
                "zone": zone, "map_id": map_id, "entity_class": kind,
                "name": item.get("Name", ""), "entity_id": item.get("EntityId", ""),
                "game_x": gx, "game_y": gy, "game_z": gz,
                "image_x": round(ix, 2) if ix != "" else "",
                "image_y": round(iy, 2) if iy != "" else "",
                "layer": item.get("Layer", ""), "entity_guid": item.get("EntityGUID", ""),
            })
            entity_counts[f"{zone}:{kind}"] += 1

    args.output.mkdir(parents=True, exist_ok=True)
    write_tsv(args.output / "client_level_objects.tsv", [
        "zone", "map_id", "object_type", "object_name", "npc_internal_name", "npc_russian_name",
        "function_type", "game_x", "game_y", "game_z", "image_x", "image_y", "subzone",
        "angles", "direction", "idle_range",
    ], objects)
    write_tsv(args.output / "client_level_entities.tsv", [
        "zone", "map_id", "entity_class", "name", "entity_id", "game_x", "game_y", "game_z",
        "image_x", "image_y", "layer", "entity_guid",
    ], entities)
    summary = {
        "source": "Aion Empire Classic client levels/<zone>/level.pak -> mission_mission0.xml",
        "zones": len({row["zone"] for row in objects}),
        "objects": len(objects),
        "entities": len(entities),
        "objects_by_zone_and_type": dict(sorted(object_counts.items())),
        "entities_by_zone_and_class": dict(sorted(entity_counts.items())),
        "image_coordinates": "included only when data/maps/maps.json contains a transform for the zone",
        "caveat": "Client-authored placements are references; server spawn rules may differ.",
    }
    (args.output / "client_level_data_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"exported {len(objects)} objects and {len(entities)} entities from {summary['zones']} zones")


if __name__ == "__main__":
    main()
