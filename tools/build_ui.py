"""Draw the rounded-corner images used by the dark theme into data/ui/*.png.

Tk cannot round corners itself, so buttons, fields, cards, tabs and counters use 9-slice images.
Corners are painted with the colour of the surface behind the widget, so no transparency is needed.
Dev tool (needs Pillow). Usage: python tools/build_ui.py
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from watcher import theme  # noqa: E402

OUT = ROOT / "data" / "ui"
SCALE = 4  # draw big, then shrink: smooth (anti-aliased) corners
RADIUS = theme.RADIUS
CARD_RADIUS = theme.CARD_RADIUS
SIZE = 48
TAB_STRIPE = 2  # px, accent bar under the selected tab


def rounded(
    name: str,
    fill: str,
    outside: str,
    radius: int,
    border: str | None = None,
    width: int = 1,
    top_only: bool = False,
    stripe: str | None = None,
) -> None:
    big = SIZE * SCALE
    image = Image.new("RGB", (big, big), outside)
    draw = ImageDraw.Draw(image)
    box = (0, 0, big - 1, big - 1 + (radius * SCALE if top_only else 0))
    if border:
        draw.rounded_rectangle(box, radius * SCALE, fill=border)
        inset = width * SCALE
        inner = (inset, inset, big - 1 - inset, box[3] - inset)
        draw.rounded_rectangle(inner, max(1, (radius - width) * SCALE), fill=fill)
    else:
        draw.rounded_rectangle(box, radius * SCALE, fill=fill)
    small = image.resize((SIZE, SIZE), Image.LANCZOS)
    if stripe:  # a bar along the bottom edge (the selected tab, UI/UX item 11), drawn after the shrink: crisp 2 px
        ImageDraw.Draw(small).rectangle((0, SIZE - TAB_STRIPE, SIZE - 1, SIZE - 1), fill=stripe)
    small.save(OUT / f"{name}.png", optimize=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    t = theme
    for outside, prefix in ((t.BG, ""), (t.SURFACE, "card_")):
        rounded(f"{prefix}btn", t.SURFACE_2, outside, RADIUS)
        rounded(f"{prefix}btn_active", t.SURFACE_3, outside, RADIUS)
        rounded(f"{prefix}btn_disabled", t.SURFACE, outside, RADIUS, border=t.SURFACE_2)
    rounded("accent", t.ACCENT, t.BG, RADIUS)
    rounded("accent_active", t.ACCENT_HOVER, t.BG, RADIUS)
    rounded("danger", t.DANGER_FILL, t.BG, RADIUS)
    rounded("danger_active", t.DANGER_FILL_HOVER, t.BG, RADIUS)
    for outside, prefix in ((t.BG, ""), (t.SURFACE, "card_")):
        rounded(f"{prefix}field", t.SURFACE_2, outside, RADIUS, border=t.BORDER_CONTROL)
        rounded(f"{prefix}field_focus", t.SURFACE_2, outside, RADIUS, border=t.ACCENT)
        rounded(f"{prefix}field_disabled", t.SURFACE, outside, RADIUS, border=t.SURFACE_2)
    rounded("card", t.SURFACE, t.BG, CARD_RADIUS)
    rounded("group", t.SURFACE_2, t.SURFACE, RADIUS)
    rounded("pill", t.SURFACE_2, t.BG, RADIUS)
    rounded("tab", t.SURFACE_2, t.BG, RADIUS, top_only=True)
    rounded("tab_active", t.SURFACE_3, t.BG, RADIUS, top_only=True)
    rounded("tab_selected", t.SURFACE, t.BG, RADIUS, top_only=True, stripe=t.ACCENT)
    print(f"wrote {len(list(OUT.glob('*.png')))} images to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
