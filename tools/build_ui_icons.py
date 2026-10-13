"""Rasterize the local Phosphor Regular SVG set into the application's small PNG icons.

Uses the local CairoSVG and Pillow copies under downloads/phosphor_icons_2.1.1/vendor/. CairoSVG needs the cairo
library and a cffi backend built for the running Python (vendor/ has the one for 3.12); where it does not load,
the icons that have an 80 px white silhouette in downloads/phosphor_icons_2.1.1/masks/ (drawn from the same SVG in
a browser canvas) are coloured from it, and the rest are left as they are.
Usage: python tools/build_ui_icons.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "downloads" / "phosphor_icons_2.1.1" / "regular"
MASKS = ROOT / "downloads" / "phosphor_icons_2.1.1" / "masks"
VENDOR = ROOT / "downloads" / "phosphor_icons_2.1.1" / "vendor"
OUTPUT = ROOT / "data" / "ui" / "icons"
TEMP = ROOT / "tmp" / "ui_icons"
try:  # the installed Pillow first: vendor/ holds builds for Python 3.12
    from PIL import Image
except ImportError:
    sys.path.insert(0, str(VENDOR))
    from PIL import Image
if str(VENDOR) not in sys.path:
    sys.path.append(str(VENDOR))

try:
    import cairosvg  # noqa: E402
except (ImportError, OSError):  # no cffi backend for this Python, or no cairo library
    cairosvg = None

ICONS = (
    "play", "arrow-up", "arrow-down", "x", "caret-right", "caret-down", "caret-up",
    "house", "minus", "plus", "crosshair", "star", "check", "circle", "check-circle", "warning",
    "magnifying-glass", "chat-circle-dots", "hourglass-medium",  # empty states (UI/UX item 12)
    "bell", "bell-fill", "map-pin", "arrow-clockwise", "funnel", "trash", "list", "pencil-simple",
)
COLORS = {
    "text": "#e9e7e4",
    "muted": "#8c919c",
    "accent": "#ff8c1a",
    "success": "#5fd38d",
    "warning": "#ff6b70",
    "caution": "#f5b544",  # theme.WARNING: «Игра не запущена», «Chat.log не найден» (UI/UX item 4)
}
SIZES = (16, 20)
LARGE = {"magnifying-glass", "chat-circle-dots", "hourglass-medium"}  # also 32 px: the picture of an empty state


def from_mask(name: str, color: str) -> Image.Image | None:
    """The icon in one solid colour from its white silhouette (alpha = shape), as CairoSVG fills currentColor."""
    path = MASKS / f"{name}_80.png"
    if not path.is_file():
        return None
    with Image.open(path) as mask:
        alpha = mask.convert("RGBA").getchannel("A")
    icon = Image.new("RGBA", alpha.size, color)
    icon.putalpha(alpha)
    return icon


def save_sizes(original: Image.Image, name: str, color_name: str) -> int:
    sizes = SIZES + ((32,) if name in LARGE else ())
    for size in sizes:
        original.resize((size, size), Image.Resampling.LANCZOS).save(OUTPUT / f"{name}_{size}_{color_name}.png",
                                                                      optimize=True)
    return len(sizes)


def main() -> None:
    missing = [name for name in ICONS if not (SOURCE / f"{name}.svg").is_file()]
    if missing:
        raise SystemExit(f"Missing source SVGs in {SOURCE}: {', '.join(missing)}")
    if TEMP.exists():
        shutil.rmtree(TEMP)
    TEMP.mkdir(parents=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    from xml.sax.saxutils import escape

    written, skipped = 0, set()
    try:
        for name in ICONS:
            for color_name, color in COLORS.items():
                if cairosvg is None:
                    icon = from_mask(name, color)
                    if icon is None:
                        skipped.add(name)
                        continue
                    written += save_sizes(icon, name, color_name)
                    continue
                svg = (SOURCE / f"{name}.svg").read_text(encoding="utf-8").replace("currentColor", escape(color))
                rendered = TEMP / f"{name}_{color_name}_4x.png"
                cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=str(rendered), output_width=80,
                                 output_height=80)
                with Image.open(rendered) as original:
                    written += save_sizes(original.convert("RGBA"), name, color_name)
    finally:
        shutil.rmtree(TEMP, ignore_errors=True)
    print(f"Generated {written} Phosphor PNGs in {OUTPUT}")
    if skipped:
        print(f"CairoSVG did not load; kept the existing PNGs of: {', '.join(sorted(skipped))}")


if __name__ == "__main__":
    main()
