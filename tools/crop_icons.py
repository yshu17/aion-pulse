"""Cut the empty margin off the client's 64×64 pictures in data/icons.

    python tools/crop_icons.py            # every picture of data/icons (and skills/, pets/); safe to repeat

The client keeps a 40×40 picture in the top left corner of a 64×64 texture; the rest is transparent. Shown in a box of one
size beside a full 56×56 picture it looks 0.6 of it, so the lists and cards read as icons of different sizes. A 64×64
picture whose visible pixels all lie in that corner is cut to 40×40; a picture that fills its texture is left as it is.
``crop_padded(path)`` is used by tools/sync_catalog_icons.py and tools/import_aiongear.py after they copy a picture.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICONS = ROOT / "data" / "icons"
TEXTURE, PICTURE = 64, 40


def crop_padded(path: Path) -> bool:
    """Cut a 64×64 picture with a 40×40 corner picture to 40×40; True when the file was changed."""
    from PIL import Image

    with Image.open(path) as opened:
        image = opened.convert("RGBA")
    if image.size != (TEXTURE, TEXTURE):
        return False
    box = image.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not box or box[2] > PICTURE + 1 or box[3] > PICTURE + 1:
        return False  # empty, or the picture fills the texture
    image.crop((0, 0, PICTURE, PICTURE)).save(path, optimize=True)
    return True


def main() -> int:
    changed = sum(crop_padded(path) for path in sorted(ICONS.rglob("*.png")))
    print(f"{changed} pictures cut to {PICTURE}x{PICTURE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
