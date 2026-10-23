"""Build data/game/ from the client exports: one command for the whole game data core.

    python tools/build_game_data.py                    # reads client_extract/*, downloads/kb_drops, writes data/game
    python tools/build_game_data.py --strict           # stop (and write nothing) when a link points to a missing ID
    python tools/build_game_data.py --out some/folder --client-build 12345

The exporters (tools/export_<section>.py) make the tables; this script joins them (core/game_data). The same tables give
the same files, byte for byte. Prints the counts and the broken links; the full report is data/game/report.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.game_data.build import BuildError, Sources, build_all  # noqa: E402


def project_sources(root: Path) -> Sources:
    """The input files of this project (the core itself computes no paths)."""
    x, d = root / "client_extract", root / "data"
    return Sources(
        items=x / "items/items.tsv", item_names=x / "items/item_names.tsv",
        legacy_item_names=d / "item_names.tsv", legacy_watch_items=d / "watch_items.csv",
        recipes=x / "recipes/recipes.tsv", recipe_ingredients=x / "recipes/recipe_ingredients.tsv",
        recipe_combinations=x / "recipes/recipe_combinations.tsv", recipe_names=x / "recipes/recipe_names.tsv",
        npcs=x / "npcs/npcs.tsv", npc_names=x / "npcs/npc_names.tsv",
        maps=x / "locations/maps.tsv", map_names=x / "locations/map_names.tsv", location_labels=x / "locations/location_labels.tsv",
        location_names=x / "locations/location_names.tsv", npc_locations=x / "locations/npc_locations.tsv",
        vendors=x / "vendors/vendors.tsv",
        quest_info=x / "raw/quest_givers.tsv", quest_npcs=x / "quests/quest_npcs.tsv", quest_rewards=x / "quests/quest_rewards.tsv",
        quest_names=x / "quests/quest_names.tsv",
        skills=x / "skills/skills.tsv", skill_names=x / "skills/skill_names.tsv", skill_learns=x / "skills/skill_learns.tsv",
        stigmas=x / "skills/stigmas.tsv", classes=x / "classes/classes.tsv", class_names=x / "classes/class_names.tsv",
        drops=root / "downloads/kb_drops/drops.tsv",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT, help="project folder (default: this project)")
    parser.add_argument("--out", type=Path, default=None, help="where to write (default: <root>/data/game)")
    parser.add_argument("--strict", action="store_true", help="stop when a link points to an ID that does not exist")
    parser.add_argument("--built", default=None, help="build date for the manifest (left out by default: the same tables give the same files)")
    parser.add_argument("--client-build", default=None, help="the client build the tables come from, if known")
    args = parser.parse_args(argv)
    out = args.out or args.root / "data" / "game"
    try:
        report = build_all(project_sources(args.root), out, built=args.built, client_build=args.client_build, strict=args.strict)
    except BuildError as error:
        print("STOPPED: links to IDs that do not exist; nothing was written")
        print(json.dumps(error.args[0]["broken_links"], ensure_ascii=False, indent=1))
        return 1
    for name, info in report["sections"].items():
        print(f"{name:<11}{info['records']:>9}" + (f"   missing: {', '.join(info['missing_inputs'])}" if info["missing_inputs"] else ""))
    print(f"{'drops':<11}{report['drops']['records']:>9}   duplicates {report['drops']['duplicates']}")
    print(f"items without a name: {report['items_without_name']}, with an older name: {report['items_with_legacy_name']}")
    for kind, entry in report["broken_links"].items():
        print(f"BROKEN {kind}: {entry['count']} (e.g. {', '.join(entry['samples'][:5])})")
    print("OK" if report["ok"] else "built, with broken links (see report.json)", "->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
