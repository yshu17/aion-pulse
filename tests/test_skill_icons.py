"""No icon is a small picture in the corner of a grey canvas.

Some skill icons came out of the client as 64x64 textures with the 40x40 art top-left and grey (130, 130, 130) around it:
in the stigma calculator they looked tiny (reported for the templar and the ranger). The art must fill the picture.
"""
from pathlib import Path

import pytest

Image = pytest.importorskip("PIL.Image")

ICONS = Path(__file__).resolve().parent.parent / "data" / "icons"
PAD = (130, 130, 130, 255)


def test_no_icon_is_padded_with_grey():
    padded = []
    for path in sorted(ICONS.rglob("*.png")):
        with Image.open(path) as source:
            width, height = source.size
            if width < 48:
                continue
            image = source.convert("RGBA")
        if all(image.getpixel(p) == PAD for p in ((width - 1, height - 1), (width - 1, 0), (0, height - 1))):
            padded.append(path.relative_to(ICONS).as_posix())
    assert padded == []
