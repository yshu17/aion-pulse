"""Export additional map data from extracted Aion client files.

This exporter is deliberately read-only for the game installation. It consumes
files under client_extract/raw and writes derived images and TSVs only there
and under client_extract/newmap and client_extract/radar.
"""

from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "client_extract" / "raw"
BASE = ROOT / "client_extract"
WORLD = RAW / "Data" / "world" / "world"
NEWMAP = RAW / "textures" / "ui" / "newmap"
RADAR_TILES = RAW / "textures" / "ui" / "zonemap"
OUT_NEWMAP = BASE / "newmap"
OUT_RADAR = BASE / "radar"
TARGET_ZONES = ("ab1", "lf1", "lf1a", "lf2", "lf2a", "lf3", "lc1", "lc2")
ZONE_IDS = {
    "ab1": "400010000", "lf1": "210010000", "lf1a": "210030000",
    "lf2": "210020000", "lf2a": "210060000", "lf3": "210040000",
    "lc1": "110010000", "lc2": "110020000",
}
NPC_COLUMNS = ["zone", "npc_id", "internal_name", "russian_name", "function_type", "ui_type", "race_type", "x", "y", "z", "source_xml"]
LABEL_COLUMNS = ["zone", "map_id", "subzone", "string_key", "name_ru", "ui_map", "x", "y", "z"]
ENTRANCE_COLUMNS = ["zone", "map_id", "name_ru", "target", "x", "y", "z", "source"]
BOSS_COLUMNS = ["zone", "map_id", "boss_raid_id", "boss_name_ru", "npc_id", "npc_internal_name", "x", "y", "z", "source"]


def read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        return reader.fieldnames or [], list(reader)


def write_tsv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def xml_root(path: Path) -> ET.Element:
    data = path.read_bytes()
    encoding = "utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") or b"\x00" in data[:100] else "utf-8-sig"
    return ET.fromstring(data.decode(encoding))


def read_names() -> dict[str, str]:
    _, rows = read_tsv(BASE / "map_strings.tsv")
    return {row["key"]: row["name"] for row in rows if row.get("key") and row.get("name")}


def stitch_tiles(folder: Path, zone: str, output: Path, prefix: str | None = None) -> bool:
    stem = prefix or zone
    tiles = [folder / f"{stem}_{i:03d}.png" for i in range(9)]
    if not all(tile.is_file() for tile in tiles):
        return False
    image = Image.new("RGB", (3072, 3072))
    for i, tile in enumerate(tiles):
        with Image.open(tile) as source:
            image.paste(source.convert("RGB"), ((i // 3) * 1024, (i % 3) * 1024))
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=94, subsampling=0)
    return True


def convert_dds_tiles() -> None:
    for source in NEWMAP.rglob("*.dds"):
        target = source.with_suffix(".png")
        if target.exists():
            continue
        with Image.open(source) as image:
            image.save(target)


def stitch_maps(zones: list[str]) -> dict[str, str]:
    status: dict[str, str] = {}
    OUT_NEWMAP.mkdir(parents=True, exist_ok=True)
    for zone in zones:
        folder = NEWMAP / zone / zone
        if zone == "ab1":
            made = [stitch_tiles(folder, zone, OUT_NEWMAP / f"ab1_{layer}.jpg", f"ab1_{layer}") for layer in (1, 2, 3)]
            status[zone] = f"{sum(made)}/3 layered mosaics"
        elif stitch_tiles(folder, zone, OUT_NEWMAP / f"{zone}.jpg"):
            status[zone] = "3x3 newmap"
        else:
            status[zone] = "no zone-wide 3x3 newmap"
    return status


def stitch_radar(zones: list[str]) -> dict[str, str]:
    status: dict[str, str] = {}
    OUT_RADAR.mkdir(parents=True, exist_ok=True)
    for zone in zones:
        files = sorted(RADAR_TILES.glob(f"pak_*/{zone}/radar_{zone}_*.png"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
        n = len(files)
        side = 32 if n == 1024 else 24 if n == 576 else 0
        if not side:
            status[zone] = f"no full-world tiles ({n})"
            continue
        tile_size = 128
        image = Image.new("RGB", (side * tile_size, side * tile_size))
        for i, path in enumerate(files):
            with Image.open(path) as tile:
                image.paste(tile.convert("RGB"), ((i // side) * tile_size, (i % side) * tile_size))
        image.save(OUT_RADAR / f"{zone}.jpg", quality=94, subsampling=0)
        status[zone] = f"{side}x{side} tiles"
    # LC2 has no world radar; preserve its four local area tiles as a 2x2 image.
    local = sorted(RADAR_TILES.glob("pak_*/lc2/radarmap_area_lc2_a/radar_radarmap_area_lc2_a_*.png"), key=lambda p: int(p.stem.rsplit("_", 1)[1]))
    if len(local) == 4:
        image = Image.new("RGB", (256, 256))
        for i, path in enumerate(local):
            with Image.open(path) as tile:
                image.paste(tile.convert("RGB"), ((i // 2) * 128, (i % 2) * 128))
        image.save(OUT_RADAR / "lc2_area.jpg", quality=94, subsampling=0)
        status["lc2_area"] = "2x2 local radar area, no world transform"
    return status


def zone_file(zone: str) -> Path | None:
    for suffix in (".txt.xml", ".xml"):
        path = WORLD / f"client_world_{zone}{suffix}"
        if path.exists():
            return path
    return None


def read_zone_data(zones: list[str]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], dict[str, dict[str, int]]]:
    _, npcs = read_tsv(BASE / "client_npcs.tsv")
    npc_by_id = {row["npc_id"]: row for row in npcs if row.get("npc_id")}
    strings = read_names()
    service_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []
    entrance_rows: list[dict[str, object]] = []
    boss_rows: list[dict[str, object]] = []
    abyss_artifact_variants: list[dict[str, object]] = []
    counts: dict[str, dict[str, int]] = {}
    for zone in zones:
        path = zone_file(zone)
        if not path:
            counts[zone] = {"npc": 0, "services": 0, "labels": 0, "entrances": 0}
            continue
        root = xml_root(path)
        subzones = root.findall("./subzones/subzone")
        services_before, labels_before, entrances_before = len(service_rows), len(label_rows), len(entrance_rows)
        for sub in subzones:
            key = sub.findtext("string", "")
            title = strings.get(key, "")
            for i, point in enumerate(sub.findall("./map_points/map_point"), start=1):
                x, y, z = (point.findtext(axis, "") for axis in ("x", "y", "z"))
                label_rows.append({"zone": zone, "map_id": ZONE_IDS[zone], "subzone": sub.findtext("name", ""), "string_key": key, "name_ru": title, "ui_map": sub.findtext("ui_map", ""), "x": x, "y": y, "z": z})
                if title.lower().startswith("вход"):
                    entrance_rows.append({"zone": zone, "map_id": ZONE_IDS[zone], "name_ru": title, "target": sub.findtext("name", ""), "x": x, "y": y, "z": z, "source": f"Data/world/world/{path.name}:subzone {sub.findtext('name','')}/map_points/map_point[{i}] (якорь подписи; точка двери не подтверждена)"})
        for npc in root.findall("./npc_infos/npc_info"):
            npc_id = npc.findtext("nameid", "")
            ref = npc_by_id.get(npc_id, {})
            pos = npc.find("pos")
            if pos is None:
                continue
            coords = {axis: pos.findtext(axis, "") for axis in ("x", "y", "z")}
            internal = ref.get("internal_name", "")
            function = ref.get("function_type", "")
            if function:
                service_rows.append({"zone": zone, "npc_id": npc_id, "internal_name": internal, "russian_name": ref.get("russian_name", ""), "function_type": function, "ui_type": ref.get("ui_type", ""), "race_type": ref.get("race_type", ""), **coords, "source_xml": path.name})
            if zone == "ab1" and ("Abyss_Artifact" in internal or "AbyssArtifact" in internal):
                abyss_artifact_variants.append({"npc_id": npc_id, "internal_name": internal, "russian_name": ref.get("russian_name", ""), **coords, "race_type": ref.get("race_type", ""), "source_xml": path.name})
            if "bossraid" in internal.lower() or "boss_raid" in internal.lower():
                match = re.search(r"(\d{4})", internal)
                boss_rows.append({"zone": zone, "map_id": ZONE_IDS[zone], "boss_raid_id": match.group(1) if match else "", "boss_name_ru": ref.get("russian_name", ""), "npc_id": npc_id, "npc_internal_name": internal, **coords, "source": f"Data/world/world/{path.name}:npc_infos/npc_info"})
        counts[zone] = {"npc": len(root.findall("./npc_infos/npc_info")), "services": len(service_rows) - services_before, "labels": len(label_rows) - labels_before, "entrances": len(entrance_rows) - entrances_before}
    # Keep the three owner/race NPC variants as one map marker per artifact.
    artifact_by_position: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for row in abyss_artifact_variants:
        artifact_by_position.setdefault((str(row["x"]), str(row["y"]), str(row["z"])), []).append(row)
    abyss_artifacts = []
    for coords, variants in artifact_by_position.items():
        base_name = re.sub(r"_(Li|Da|Dr)$", "", str(variants[0]["internal_name"]))
        abyss_artifacts.append({
            "internal_name": base_name,
            "x": coords[0], "y": coords[1], "z": coords[2],
            "npc_ids": ",".join(str(v["npc_id"]) for v in variants),
            "race_types": ",".join(str(v["race_type"]) for v in variants),
            "source_xml": "client_world_ab1.xml:npc_infos/npc_info (owner variants collapsed by shared coordinates)",
        })
    return service_rows, label_rows, entrance_rows, boss_rows, abyss_artifacts, counts


def merge_rows(path: Path, columns: list[str], rows: list[dict[str, object]], key_columns: tuple[str, ...]) -> int:
    _, old = read_tsv(path)
    keys = {tuple(row.get(c, "") for c in key_columns) for row in old}
    added = 0
    for row in rows:
        key = tuple(str(row.get(c, "")) for c in key_columns)
        if key not in keys:
            old.append({c: str(row.get(c, "")) for c in columns})
            keys.add(key)
            added += 1
    write_tsv(path, columns, old)
    return added


def export_data(zones: list[str]) -> dict[str, object]:
    service, labels, entrances, bosses, artifacts, counts = read_zone_data(zones)
    service_added = merge_rows(RAW / "npc_service_coords.tsv", NPC_COLUMNS, service, ("zone", "npc_id", "x", "y", "z"))
    # Backfill faction/race from the full NPC catalog for older rows too.
    _, npc_catalog = read_tsv(BASE / "client_npcs.tsv")
    race_by_id = {row["npc_id"]: row.get("race_type", "") for row in npc_catalog if row.get("npc_id")}
    npc_path = RAW / "npc_service_coords.tsv"
    _, all_services = read_tsv(npc_path)
    for row in all_services:
        row["race_type"] = race_by_id.get(row.get("npc_id", ""), row.get("race_type", ""))
    write_tsv(npc_path, NPC_COLUMNS, all_services)
    label_added = merge_rows(RAW / "subzone_labels.tsv", LABEL_COLUMNS, labels, ("zone", "subzone", "x", "y", "z"))
    entrance_added = merge_rows(RAW / "dungeon_entrances.tsv", ENTRANCE_COLUMNS, entrances, ("zone", "target", "x", "y", "z"))
    boss_added = merge_rows(RAW / "raid_boss_spawns.tsv", BOSS_COLUMNS, bosses, ("zone", "npc_id", "x", "y", "z"))
    if artifacts:
        write_tsv(RAW / "abyss_artifacts.tsv", ["internal_name", "x", "y", "z", "npc_ids", "race_types", "source_xml"], artifacts)
    # Fortress polygons are the authoritative location available in world XML; there are no direct gatecontroller placements here.
    root = xml_root(WORLD / "client_world_ab1.xml") if "ab1" in zones else None
    fortress_rows = []
    if root is not None:
        for area in root.findall("./abyss_castle_areas/abyss_castle_area"):
            info = area.find("points_info")
            fortress_rows.append({"name": area.findtext("name", ""), "abyss_id": area.findtext("abyss_id", ""), "bottom": info.findtext("bottom", "") if info is not None else "", "top": info.findtext("top", "") if info is not None else "", "points_xy": ";".join(f"{p.findtext('x','')},{p.findtext('y','')}" for p in area.findall("./points_info/points/data")), "source_xml": "client_world_ab1.xml:abyss_castle_areas"})
    if fortress_rows:
        write_tsv(RAW / "abyss_fortress_areas.tsv", ["name", "abyss_id", "bottom", "top", "points_xy", "source_xml"], fortress_rows)
    mission = RAW / "levels" / "ab1" / "mission_mission0.xml"
    gate_rows: list[dict[str, object]] = []
    placed_artifacts: list[dict[str, object]] = []
    if "ab1" in zones and mission.exists():
        mission_root = xml_root(mission)
        entities = mission_root.findall(".//Entity")
        artifact_groups: dict[str, list[dict[str, str]]] = defaultdict(list)
        for entity in entities:
            name = entity.get("Name", "")
            entity_class = entity.get("EntityClass", "")
            pos = entity.get("Pos", "").split(",")
            if len(pos) != 3:
                continue
            x, y, z = (value.strip() for value in pos)
            if entity_class == "PlaceableObject" and re.match(r"^Ab1_\d+_Gatecontrol", name, re.I):
                gate_rows.append({"name": name, "entity_id": entity.get("EntityId", ""), "x": x, "y": y, "z": z, "layer": entity.get("Layer", ""), "source_xml": "levels/ab1/mission_mission0.xml"})
            if entity_class == "AbyssArtifacts" and name.startswith("Artifact_"):
                key = re.sub(r"_(Li|Da|Dr)$", "", name)
                artifact_groups[key].append({"name": name, "entity_id": entity.get("EntityId", ""), "x": x, "y": y, "z": z, "layer": entity.get("Layer", ""), "race": name.rsplit("_", 1)[-1]})
        for name, variants in sorted(artifact_groups.items()):
            first = variants[0]
            placed_artifacts.append({"name": name, "x": first["x"], "y": first["y"], "z": first["z"], "entity_names": ",".join(v["name"] for v in variants), "entity_ids": ",".join(v["entity_id"] for v in variants), "race_variants": ",".join(v["race"] for v in variants), "layer": first["layer"], "source_xml": "levels/ab1/mission_mission0.xml:Entity"})
        write_tsv(RAW / "abyss_gatecontrols.tsv", ["name", "entity_id", "x", "y", "z", "layer", "source_xml"], gate_rows)
        write_tsv(RAW / "abyss_artifacts.tsv", ["name", "x", "y", "z", "entity_names", "entity_ids", "race_variants", "layer", "source_xml"], placed_artifacts)
    layer_rows = []
    abyss_config = WORLD / "client_abyss.txt.xml"
    if "ab1" in zones and abyss_config.exists():
        for item in xml_root(abyss_config).findall("./client_abyss"):
            if item.findtext("world", "").lower() == "ab1":
                layer_rows.append({"abyss_id": item.findtext("id", ""), "internal_name": item.findtext("name", ""), "abyss_type": item.findtext("abyss_type", ""), "map_layer": item.findtext("map_layer", ""), "description_key": item.findtext("desc", "")})
        write_tsv(RAW / "abyss_layer_areas.tsv", ["abyss_id", "internal_name", "abyss_type", "map_layer", "description_key"], layer_rows)
    frame_rows = []
    zonemap = xml_root(WORLD / "zonemap.xml")
    for item in zonemap.findall(".//zonemap"):
        zone = item.findtext("name", "").lower()
        if zone not in zones:
            continue
        frame_rows.append({"zone": zone, "map_id": item.findtext("id", ""), "world_width": item.findtext("world_width", ""), "world_height": item.findtext("world_height", ""), "offset_x": item.findtext("offset_x", "0"), "offset_y": item.findtext("offset_y", "0"), "map_width": item.findtext("map_width", item.findtext("world_width", "")), "map_height": item.findtext("map_height", item.findtext("world_height", ""))})
    frames_path = RAW / "zone_map_frames.tsv"
    frame_columns = ["zone", "map_id", "world_width", "world_height", "offset_x", "offset_y", "map_width", "map_height"]
    _, existing_frames = read_tsv(frames_path)
    existing_frames = [row for row in existing_frames if row.get("zone") not in zones]
    write_tsv(frames_path, frame_columns, existing_frames + frame_rows)
    return {"counts": counts, "added": {"services": service_added, "labels": label_added, "entrances": entrance_added, "bosses": boss_added}, "abyss_artifact_markers": len(placed_artifacts) or len(artifacts), "abyss_gatecontrols": len(gate_rows), "abyss_fortress_areas": len(fortress_rows), "abyss_layer_areas": len(layer_rows), "map_frames": len(frame_rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zones", default=",".join(TARGET_ZONES), help="comma-separated world codes")
    parser.add_argument("--no-images", action="store_true", help="skip DDS conversion and image mosaics")
    args = parser.parse_args()
    zones = [z.strip().lower() for z in args.zones.split(",") if z.strip()]
    if not args.no_images:
        convert_dds_tiles()
        maps = stitch_maps(zones)
        radar = stitch_radar([z for z in zones if z != "ab1"] + (["ab1"] if "ab1" in zones else []))
    else:
        maps, radar = {}, {}
    result = export_data(zones)
    print({"maps": maps, "radar": radar, **result})


if __name__ == "__main__":
    main()
