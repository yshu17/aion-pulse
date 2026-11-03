"""Build data/pulse.db, the one game database every tab of Pulse+ reads (docs/ADR-002-pulse-db.md, core/pulse_db).

Run after the map's, the game data's or the bestiary's files change (tools/import_missing_maps.py, build_game_data.py,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "pulse.db")
    args = parser.parse_args(argv)
    data = ROOT / "data"
    sources = Sources(spawns=data / "maps" / "spawns.json", npc_points=data / "game" / "npc_points.json.gz",
                      npcs=data / "game" / "npcs.json.gz", bestiary=data / "bestiary" / "npcs.sqlite")
    report = build(sources, args.out)
    print(f"{args.out}: {report['npcs']} NPCs, {report['aliases']} map markers linked, {report['points']} points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
