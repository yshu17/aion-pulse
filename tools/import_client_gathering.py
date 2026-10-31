"""Add the client's gathering nodes (all skill levels) of every zone and dungeon with a map to data/maps/gathering.json.

aion-map.vercel.app (tools/import_gathering.py) covers ten open zones and the Abyss; the client has the rest: Inggison,
Gelkmaros, Sarpan, Tiamaranta, the dungeons (Araka, …) and the spots the site lacks. The client keeps them as «HSP»
objects of each level («levels/<zone>/level.pak», mission_mission0.xml) named after a resource of
data/gather/gather.pak (gather_src.xml): its skill level, its kind (aether: «aerial_gathering»), its drops. The game
folder is only read; the reading of its archives is tools/sync_client_gathering.py (Codex).

The site's resources stay as they are; a client resource with the same name, level, kind and layer adds only spots
the site lacks (0.16 m apart or more), the others come in as new resources. Names: the client's Russian strings.
Icons: the client's item icon of the first drop found (client_<icon>.png, 64 px). The Abyss gets its layer by height
as its points (1: below 2000 m, 2: below 2550 m, 3: above); a dungeon with several floor pictures has no height bounds
in the client: its spots go on every floor (layer null).

Writes: data/maps/gathering.json (the same format), data/maps/gathering/client_*.png. Re-running starts again from
the site's files (tools/import_gathering.py runs first). Prints what it added per zone.
Dev tool. Usage: python tools/import_client_gathering.py [--game <classic folder>] [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import import_gathering  # noqa: E402
from sync_client_gathering import (GAME, archive_file, catalog, choose_icon, closed_beta_table,  # noqa: E402
                                   item_icons, iter_pak_entries, layer_for, merge_nodes, resolve_source,
                                   russian_strings)
import xml.etree.ElementTree as ET  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAPS = ROOT / "data" / "maps"


def level_folders(game: Path) -> dict[str, str]:
    """Map id → the client's level folder, from the zone's picture name («client/idelemental_2_1.jpg»: idelemental_2)."""
    zones = json.loads((MAPS / "maps.json").read_text(encoding="utf-8"))
    out = {}
    for map_id, zone in zones.items():
        if not isinstance(zone, dict) or not zone.get("file"):
            continue
        stem = Path(zone["file"]).stem
        for name in (stem, re.sub(r"_\d+$", "", stem), stem.removesuffix("_radar")):
            if (game / "levels" / name / "level.pak").exists():
                out[map_id] = name
                break
    return out


def drop_names() -> dict[str, str]:
    """An item's internal name → its Russian name (client_extract/items/items.tsv, data/game/items.json.gz)."""
    with gzip.open(ROOT / "data/game/items.json.gz", "rt", encoding="utf-8") as stream:
        names = {row["id"]: row["name"] for row in json.load(stream)["records"] if row.get("name")}
    with (ROOT / "client_extract/items/items.tsv").open(encoding="utf-8", newline="") as stream:
        return {row["internal_name"].casefold(): names[row["item_id"]]
                for row in csv.DictReader(stream, delimiter="\t") if row["item_id"] in names}


def node_name(source: dict, strings: dict[str, str], drops: dict[str, str]) -> str:
    """The resource's Russian name; without one (Araka's trees), its drops («Сломанный древесный ствол / Причудливый ключ»)."""
    name = strings.get(source.get("desc", "").casefold())
    if name:
        return name
    found = [drops[m.casefold()] for i in range(1, 9) if (m := source.get(f"material{i}")) and m.casefold() in drops]
    return " / ".join(dict.fromkeys(found)) or source["name"]


def client_nodes(game: Path, table: bytes, folders: dict[str, str]) -> tuple[dict, Counter]:
    sources = catalog(game, table)
    strings = russian_strings()
    drops = drop_names()
    icons = item_icons()
    available = {Path(name).stem.casefold() for name, _ in
                 iter_pak_entries(game / "data/items/items.pak", table) if name.casefold().endswith(".dds")}
    grouped: dict[tuple, dict] = {}
    skipped = Counter()
    for map_id, folder in sorted(folders.items()):
        try:
            mission = ET.fromstring(archive_file(game / "levels" / folder / "level.pak", table, "mission_mission0.xml"))
        except FileNotFoundError:
            continue
        for obj in mission.iter("Object"):
            if obj.get("Type") != "HSP":
                continue
            source = resolve_source((obj.get("npc") or "").casefold(), sources)
            pos = (obj.get("Pos") or "").split(",")
            if source is None or len(pos) != 3:
                skipped[f"{folder}:{'no_catalog' if source is None else 'bad_position'}"] += 1
                continue
            x, y, z = map(float, pos)
            layer = layer_for(z) if map_id == "400010000" else None
            key = map_id, source["id"], layer
            if key not in grouped:
                ru = node_name(source, strings, drops)
                icon, _ = choose_icon(source, icons, available)
                grouped[key] = {
                    "id": source["id"], "name": ru, "name_en": "",  # the client has no English name, only its own
                    "kind": "aether" if source.get("harvestskill") == "aerial_gathering" else "essence",
                    "type": source.get("source_type", ""), "level": int(source.get("skill_level") or 0),
                    "icon": f"client_{icon}" if icon else "", "layer": layer, "points": [],
                }
            point = [round(x, 1), round(y, 1)]
            if point not in grouped[key]["points"]:
                grouped[key]["points"].append(point)
    nodes: dict[str, list[dict]] = defaultdict(list)
    for (map_id, _, _), node in grouped.items():
        nodes[map_id].append(node)
    return dict(nodes), skipped


def drop_renamed(site: dict, client: dict) -> int:
    """Leave out client resources the site has under another name (its «Фруктовое дерево» is the site's «Мелла»):
    every spot at a spot of a site resource of the same level, kind and layer. Returns how many were left out."""
    dropped = 0
    for map_id, nodes in client.items():
        kept = []
        for node in nodes:
            same = [n for n in site.get(map_id, []) if (n["level"], n["kind"], n["layer"]) ==
                    (node["level"], node["kind"], node["layer"]) and n["name"].casefold() != node["name"].casefold()]
            spots = [{(round(x), round(y)) for x, y in n["points"]} for n in same]
            if any(all((round(x), round(y)) in s for x, y in node["points"]) for s in spots):
                dropped += 1
            else:
                kept.append(node)
        client[map_id] = kept
    return dropped


def save_icons(game: Path, table: bytes, needed: set[str]) -> list[str]:
    """The client's item icons the nodes name, as PNG next to the site's; returns the ones not found."""
    dest = MAPS / "gathering"
    dest.mkdir(exist_ok=True)
    wanted = {name.removeprefix("client_") + ".dds": name for name in needed}
    for filename, raw in iter_pak_entries(game / "data/items/items.pak", table):
        icon = wanted.get(filename.casefold())
        if icon and not (dest / f"{icon}.png").exists():
            with Image.open(io.BytesIO(raw)) as image:
                rgba = image.convert("RGBA")
                # the client's texture is 64 px with the 40 px icon in its corner: cut to it, as the site's icons
                rgba.crop(rgba.getchannel("A").getbbox() or (0, 0, *rgba.size)).save(dest / f"{icon}.png")
    return sorted(name for name in needed if not (dest / f"{name}.png").exists())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", type=Path, default=GAME)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    table = closed_beta_table(ROOT / "downloads/aion_map_extract/PakConstants.java")
    site = import_gathering.build(import_gathering.SOURCE)["zones"]
    folders = level_folders(args.game)
    client, skipped = client_nodes(args.game, table, folders)
    renamed = drop_renamed(site, client)
    merged, stats = merge_nodes(site, client)
    stats["renamed_left_out"] = renamed
    for nodes in merged.values():
        for node in nodes:
            node.pop("source", None)
        nodes.sort(key=lambda n: (n["kind"] != "essence", n["level"], n["name"], n["layer"] or 0))
    for map_id in sorted(merged):
        before = sum(len(n["points"]) for n in site.get(map_id, []))
        after = sum(len(n["points"]) for n in merged[map_id])
        if after != before:
            print(f"{map_id} {folders.get(map_id, '?')}: {len(merged[map_id])} resources, {before} -> {after} spots")
    print(json.dumps(stats), "skipped:", dict(skipped.most_common(12)))
    if args.dry_run:
        return
    needed = {n["icon"] for nodes in merged.values() for n in nodes if n["icon"].startswith("client_")}
    missing = save_icons(args.game, table, needed)
    for nodes in merged.values():
        for node in nodes:
            if node["icon"] in missing:
                node["icon"] = ""
    (MAPS / "gathering.json").write_text(json.dumps({"version": 1, "zones": merged}, ensure_ascii=False,
                                                    separators=(",", ":")), encoding="utf-8")
    print(f"{len(merged)} zones written; icons not in the client: {missing or 'none'}")


if __name__ == "__main__":
    main()
