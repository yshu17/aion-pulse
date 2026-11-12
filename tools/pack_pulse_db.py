"""Pack data/pulse.db as a release file of its own (docs/ADR-003-pulse-db-replace.md).

    python tools/pack_pulse_db.py [--tag db-latest] [--repo yshu17/aion-pulse] [--out local/PulseDb]

Writes local/PulseDb/pulse-db-<id>.zip and local/PulseDb/db_pack.json, and data/db_pack.json (the record of the pack the bundled
pulse.db is: the program compares it with the one on the release). To publish a new database upload BOTH files of local/PulseDb
to the release «db-latest» (replace the old db_pack.json); programs that carry an older database offer the update. Nothing is
uploaded by this script. A pack of the same pulse.db is not built again: the record keeps its time.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pulse_db.pack import make_pack, write_record  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", default="db-latest")
    parser.add_argument("--repo", default="yshu17/aion-pulse")
    parser.add_argument("--out", type=Path, default=ROOT / "local" / "PulseDb")
    args = parser.parse_args()
    db = ROOT / "data" / "pulse.db"
    if not db.is_file():
        print(f"{db} is missing: run tools/build_pulse_db.py first", file=sys.stderr)
        return 1
    record_path = ROOT / "data" / "db_pack.json"
    previous = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = make_pack(db, args.out, args.tag, args.repo, previous, now)
    write_record(record, args.out / "db_pack.json", record_path)
    print(f"pack {record['name']} schema {record['schema']} built {record['built']} {record['size'] / 1048576:.1f} MB -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
