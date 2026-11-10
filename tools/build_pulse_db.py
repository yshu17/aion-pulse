"""Build data/pulse.db, the one game database every tab of Pulse+ reads (docs/ADR-002-pulse-db.md, core/pulse_db).

Run after the map's, the game data's, the bestiary's or the item files change (tools/import_missing_maps.py, build_game_data.py,
copy_bestiary_data.py). data/pulse.db is not in git; the build of the program packs it with the rest of data/.
Usage: python tools/build_pulse_db.py [--out data/pulse.db]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pulse_db.build import Sources, build  # noqa: E402


def bestiary_source() -> Path:
    """The bestiary's index as built (local/bestiary), else its copy in data/bestiary (a tree without local/)."""
    built = ROOT / "local" / "bestiary" / "npcs.sqlite"
    return built if built.is_file() else ROOT / "data" / "bestiary" / "npcs.sqlite"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "pulse.db")
    args = parser.parse_args(argv)
    data = ROOT / "data"
    sources = Sources(spawns=data / "maps" / "spawns.json", npc_points=data / "game" / "npc_points.json.gz",
                      npcs=data / "game" / "npcs.json.gz", bestiary=bestiary_source(),
                      item_names=data / "item_names.tsv", catalog=data / "watch_items.csv", specs=data / "item_specs.json.gz",
                      items=data / "game" / "items.json.gz", quests=data / "game" / "quests.json.gz", quest_names=data / "quest_names.tsv",
                      recipes=data / "game" / "recipes.json.gz", vendors=data / "game" / "vendors.json.gz",
                      client_catalog=ROOT / "client_extract" / "fresh_catalog" / "catalog.sqlite", icons=data / "icons",
                      quest_dir=ROOT / "client_extract" / "raw" / "Data" / "quest",
                      aidb_pages=ROOT / "downloads" / "aidb_quests" / "pages",
                      client_raw=ROOT / "client_extract" / "fresh_catalog" / "raw")
    report = build(sources, args.out)
    print(f"{args.out}: {report['npcs']} NPCs ({report['listed']} in the bestiary), {report['aliases']} map markers linked, "
          f"{report['points']} points, {report['items']} items ({report['catalog']} with a card), {report['drops']} drops, {report['stock']} goods, "
          f"{report['quests']} quests, {report['recipes']} recipes, {report['vendor_items']} vendor items, "
          f"{report['titles']} titles, {report['skills']} skills, {report['skill_books']} skill books, {report['stigmas']} stigmas, "
          f"{report['pets']} pets, {report['quest_steps']} quests with steps, {report['quest_guides']} guides, {report['gear_items']} gear items")
    print("sections:", ", ".join(f"{key} {count}" for key, count in report["sections"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
