"""Rasterize the local Phosphor Regular SVG set into the application's small PNG icons.

Uses the local CairoSVG and Pillow copies under downloads/phosphor_icons_2.1.1/vendor/.
Usage: python tools/build_ui_icons.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "downloads" / "phosphor_icons_2.1.1" / "regular"
VENDOR = ROOT / "downloads" / "phosphor_icons_2.1.1" / "vendor"
OUTPUT = ROOT / "data" / "ui" / "icons"
TEMP = ROOT / "tmp" / "ui_icons"
sys.path.insert(0, str(VENDOR))

import cairosvg  # noqa: E402
from PIL import Image  # noqa: E402

ICONS = (
    "play", "arrow-up", "arrow-down", "x", "caret-right", "caret-down", "caret-up",
    "house", "minus", "plus", "crosshair", "star", "check", "circle", "check-circle", "warning",
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


def main() -> None:
    missing = [name for name in ICONS if not (SOURCE / f"{name}.svg").is_file()]
    if missing:
        raise SystemExit(f"Missing source SVGs in {SOURCE}: {', '.join(missing)}")
    if TEMP.exists():
        shutil.rmtree(TEMP)
    TEMP.mkdir(parents=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    from xml.sax.saxutils import escape

    entries = [(name, color_name, color) for name in ICONS for color_name, color in COLORS.items()]
    try:
        for name, color_name, color in entries:
            source = (SOURCE / f"{name}.svg").read_text(encoding="utf-8")
            svg = source.replace("currentColor", escape(color))
            rendered = TEMP / f"{name}_{color_name}_4x.png"
            cairosvg.svg2png(
                bytestring=svg.encode("utf-8"), write_to=str(rendered), output_width=80, output_height=80
            )
            with Image.open(rendered) as original:
                original = original.convert("RGBA")
                for size in SIZES:
                    icon = original.resize((size, size), Image.Resampling.LANCZOS)
                    icon.save(OUTPUT / f"{name}_{size}_{color_name}.png", optimize=True)
    finally:
        shutil.rmtree(TEMP, ignore_errors=True)
    print(f"Generated {len(entries) * len(SIZES)} Phosphor PNGs in {OUTPUT}")


if __name__ == "__main__":
    main()
