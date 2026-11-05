"""Fill data/icons with the item pictures the game folder lacks, in the one style of the others (56x56, art to the edge).

The pulse.db items name a picture in data/icons (the same files the chat and the item list show). A few hundred of them are
only in the bestiary's pictures: data/bestiary/icons/client/*.png (64x64, the art 40x40 in the top-left corner on a
transparent canvas) and data/bestiary/icons/items/*.jpg (the site's: 64x64 or the art 40x40 on a flat black or grey). Shown as they are
they look smaller and framed next to the rest. This cuts the art out of each and scales it to 56x56, once.
Dev tool (needs Pillow, numpy and data/pulse.db). Usage: python tools/fill_item_icons.py [--dry-run]
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SIZE = 56
TOLERANCE = 12  # a jpg's padding is one flat colour (black or grey): a pixel that differs from it by more is art


def art_box(image: Image.Image, is_png: bool) -> tuple[int, int, int, int]:
    """The rectangle of the art: the opaque part of a png, the part of a jpg that is not its flat padding colour."""
    rgba = image.convert("RGBA")
    if is_png and rgba.getchannel("A").getbbox() not in (None, (0, 0, *rgba.size)):
        return rgba.getchannel("A").getbbox()
    pixels = np.asarray(rgba.convert("RGB")).astype(int)
    padding = pixels[-1, -1]  # the corner farthest from the art
    ys, xs = np.where(np.abs(pixels - padding).max(axis=2) > TOLERANCE)
    if not len(xs):
        return (0, 0, *rgba.size)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def normalized(path: Path) -> Image.Image:
    image = Image.open(path)
    rgba = image.convert("RGBA").crop(art_box(image, path.suffix == ".png"))
    return rgba.convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)


def missing(db: sqlite3.Connection, icons: Path) -> list[str]:
    """Pictures the items name (the goods of merchants and the drops) that data/icons does not have."""
    have = {f.stem.lower() for f in icons.glob("*.png")}
    names = {name.strip() for (name,) in db.execute(
        "SELECT DISTINCT i.icon FROM item i WHERE i.icon IS NOT NULL AND (i.dropped_by IS NOT NULL OR i.id IN "
        "(SELECT CAST(item_id AS INTEGER) FROM npc_stock))")}
    return sorted(name.lower() for name in names if name.lower() not in have)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    icons = ROOT / "data" / "icons"
    bestiary = ROOT / "data" / "bestiary" / "icons"
    made, nowhere = 0, []
    with sqlite3.connect(ROOT / "data" / "pulse.db") as db:
        for name in missing(db, icons):
            source = next((p for p in (bestiary / "client" / f"{name}.png", bestiary / "items" / f"{name}.jpg") if p.is_file()), None)
            if source is None:
                nowhere.append(name)
                continue
            if not args.dry_run:
                normalized(source).save(icons / f"{name}.png", optimize=True)
            made += 1
    print(f"{made} pictures {'would be ' if args.dry_run else ''}made in data/icons; none in the bestiary's folders: {nowhere}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
