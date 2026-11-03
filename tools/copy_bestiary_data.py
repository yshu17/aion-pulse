"""Copy the bestiary's database and pictures into data/bestiary, the folder the launcher ships (Pulse+.exe packs data/).

The database is built by tools/build_bestiary_index.py into local/bestiary/npcs.sqlite; the pictures come from
tools/fetch_bestiary_icons.py into local/bestiary/icons. data/bestiary is not in git (about 55 MB): run this before a
build. Usage: python tools/copy_bestiary_data.py [--source local/bestiary] [--target data/bestiary]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_FOLDERS = ("npc", "client", "items")


def copy_bestiary(source: Path, target: Path) -> tuple[int, int]:
    """Copy npcs.sqlite and the icon folders; returns (files copied, bytes)."""
    database = source / "npcs.sqlite"
    if not database.is_file():
        raise FileNotFoundError(f"no database: {database}")
    target.mkdir(parents=True, exist_ok=True)
    files = [(database, target / "npcs.sqlite")]
    for folder in ICON_FOLDERS:
        for picture in sorted((source / "icons" / folder).glob("*")):
            if picture.is_file():
                files.append((picture, target / "icons" / folder / picture.name))
    size = 0
    for src, dst in files:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        size += src.stat().st_size
    return len(files), size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, default=ROOT / "local" / "bestiary")
    parser.add_argument("--target", type=Path, default=ROOT / "data" / "bestiary")
    args = parser.parse_args(argv)
    try:
        count, size = copy_bestiary(args.source, args.target)
    except FileNotFoundError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{count} files, {size / 1024 / 1024:.1f} MB -> {args.target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
