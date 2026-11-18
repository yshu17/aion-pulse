"""Cut the stigma window's pictures out of the game client's UI atlases into data/ui/stigma (the stigma calculator's slots).

    py -3 tools/import_stigma_ui.py        (needs Pillow)

Source: client_extract/raw/textures/ui/ui/v4_popup1.png (the stigma window: the slot frames) and v4_common_1.png (the abyss
point coin). The boxes were found by eye on 17.11.2026 and checked by the frame's opaque area; the pictures are the client's own.

Out: data/ui/stigma/normal.png, normal_on.png (gold, empty and lit), advanced.png, advanced_on.png (blue), locked.png (grey),
ap.png (the coin).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "client_extract" / "raw" / "textures" / "ui" / "ui"
OUT = ROOT / "data" / "ui" / "stigma"
# atlas, box (left, top, right, bottom)
CUTS = {
    "normal": ("v4_popup1.png", (370, 80, 453, 160)),
    "advanced": ("v4_popup1.png", (453, 80, 537, 160)),
    "normal_on": ("v4_popup1.png", (370, 160, 453, 240)),
    "advanced_on": ("v4_popup1.png", (453, 160, 537, 240)),
    "locked": ("v4_popup1.png", (437, 0, 522, 80)),
    "ap": ("v4_common_1.png", (132, 163, 176, 209)),
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (atlas, box) in CUTS.items():
        piece = Image.open(UI / atlas).convert("RGBA").crop(box)
        bbox = piece.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        piece = piece.crop(bbox) if bbox else piece
        piece.save(OUT / f"{name}.png", optimize=True)
        print(f"{name}: {piece.size[0]}x{piece.size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
