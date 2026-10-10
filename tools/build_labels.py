"""Build data/maps/labels.tsv (area names on the map) from the client's own subzone labels.

Input: client_extract/raw/subzone_labels.tsv by Codex — one row per <map_point> of a <subzone> in
client_world_<zone>.xml: where the game itself writes the area's name, with ui_map telling on which view.
Output rows: map_id, level, game x, game y, name. Levels: «main» names are drawn on the whole zone map,
«zoom» names (and «fly_path», the flight-route stops) only closer in; «none» and empty ui_map are not shown
by the game and are left out. Long names get a line break («|») at the middle space.
Dev tool. Usage: python tools/build_labels.py
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "client_extract" / "raw" / "subzone_labels.tsv"
OUT = ROOT / "data" / "maps" / "labels.tsv"
LEVELS = {"main": "main", "zoom": "zoom", "fly_path": "zoom"}
WRAP = 18  # characters: longer names go on two lines


def wrap(name: str) -> str:
    if len(name) <= WRAP or " " not in name:
        return name
    spaces = [i for i, ch in enumerate(name) if ch == " "]
    cut = min(spaces, key=lambda i: abs(i - len(name) / 2))
    return name[:cut] + "|" + name[cut + 1:]


def labels(rows: list[dict]) -> list[tuple[str, str, float, float, str]]:
    """(map id, level, game x, game y, name) for the shown rows, without repeats of one name at one spot."""
    out, seen = [], set()
    for row in rows:
        level = LEVELS.get(row["ui_map"].strip())
        name = " ".join(row["name_ru"].split())
        if level is None or not name:
            continue
        x, y = round(float(row["x"]), 1), round(float(row["y"]), 1)
        key = (row["map_id"], name, round(x), round(y))
        if key not in seen:
            seen.add(key)
            out.append((row["map_id"], level, x, y, wrap(name)))
    return out


def main() -> int:
    with open(SOURCE, encoding="utf-8-sig", newline="") as f:
        rows = labels(list(csv.DictReader(f, delimiter="\t")))
    lines = ["# Area names from the client: <subzone><map_point> of client_world_*.xml (tools/build_labels.py).",
             "# map_id<TAB>level (main — whole map, zoom — closer in)<TAB>game x<TAB>game y<TAB>name («|» = line break)"]
    lines += [f"{map_id}\t{level}\t{x}\t{y}\t{name}" for map_id, level, x, y, name in sorted(rows)]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rows)} labels -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
