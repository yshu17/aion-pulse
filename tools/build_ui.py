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
DPI_VARIANTS = ((1.0, ""), (1.25, "@125"), (1.5, "@150"), (2.0, "@2x"))
TAB_STRIPE = 2  # px, accent bar under the selected tab
SCROLLBAR_WIDTH = 8
SCROLLBAR_HEIGHT = 24
SCALE_TRACK_WIDTH = 12
SCALE_TRACK_HEIGHT = 6
SCALE_THUMB_SIZE = 16


def rounded(
    name: str,
    fill: str,
    outside: str,
    radius: int,
    border: str | None = None,
    width: int = 1,
    top_only: bool = False,
    stripe: str | None = None,
    top_edge: bool = False,
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
    for factor, suffix in DPI_VARIANTS:
        target = round(SIZE * factor)
        rendered = image.resize((target, target), Image.Resampling.LANCZOS)
        draw_rendered = ImageDraw.Draw(rendered)
        if stripe:  # UI/UX item 11: keep the selected-tab bar crisp at each DPI
            stripe_height = max(1, round(TAB_STRIPE * factor))
            draw_rendered.rectangle((0, target - stripe_height, target - 1, target - 1), fill=stripe)
        if top_edge:  # UI/UX item 20: crisp 1 logical px, kept inside the rounded corners
            edge_color = tuple(round(channel + (255 - channel) * 0.10) for channel in _rgb(border or fill))
            inset = min(round(radius * factor), target // 4)
            draw_rendered.line(
                (inset, 0, target - inset - 1, 0),
                fill=edge_color,
                width=max(1, round(factor)),
            )
        rendered.save(OUT / f"{name}{suffix}.png", optimize=True)


def _rgb(color: str) -> tuple[int, int, int]:
    """Parse a theme hex colour for small derived image highlights."""
    return tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))


def scrollbar_thumb(name: str, fill: str) -> None:
    """Draw an 8px transparent scrollbar thumb; Tk stretches only its straight center."""
    big_w, big_h = SCROLLBAR_WIDTH * SCALE, SCROLLBAR_HEIGHT * SCALE
    image = Image.new("RGBA", (big_w, big_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = 2 * SCALE
    draw.rounded_rectangle(
        (inset, 0, big_w - inset - 1, big_h - 1),
        radius=2 * SCALE,
        fill=fill,
    )
    image.resize((SCROLLBAR_WIDTH, SCROLLBAR_HEIGHT), Image.Resampling.LANCZOS).save(
        OUT / f"{name}.png", optimize=True
    )


def scale_track() -> None:
    """Draw the thin, rounded track used by ttk's horizontal scale."""
    width, height = SCALE_TRACK_WIDTH * SCALE, SCALE_TRACK_HEIGHT * SCALE
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=height // 2, fill=theme.SURFACE_2)
    image.resize((SCALE_TRACK_WIDTH, SCALE_TRACK_HEIGHT), Image.Resampling.LANCZOS).save(
        OUT / "scale_track.png", optimize=True
    )


def scale_thumb(name: str, fill: str) -> None:
    """Draw an antialiased circular scale thumb with a quiet outline."""
    size = SCALE_THUMB_SIZE * SCALE
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    inset = SCALE * 1.5
    draw.ellipse((inset, inset, size - inset - 1, size - inset - 1), fill=fill, outline=theme.BG, width=SCALE)
    image.resize((SCALE_THUMB_SIZE, SCALE_THUMB_SIZE), Image.Resampling.LANCZOS).save(
        OUT / f"{name}.png", optimize=True
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    t = theme
    for outside, prefix in ((t.BG, ""), (t.SURFACE, "card_")):
        rounded(f"{prefix}btn", t.SURFACE_2, outside, RADIUS, top_edge=True)
        rounded(f"{prefix}btn_active", t.SURFACE_3, outside, RADIUS, top_edge=True)
        rounded(f"{prefix}btn_disabled", t.SURFACE, outside, RADIUS, border=t.SURFACE_2, top_edge=True)
    rounded("accent", t.ACCENT, t.BG, RADIUS, top_edge=True)
    rounded("accent_active", t.ACCENT_HOVER, t.BG, RADIUS, top_edge=True)
    rounded("danger", t.DANGER_FILL, t.BG, RADIUS, top_edge=True)
    rounded("danger_active", t.DANGER_FILL_HOVER, t.BG, RADIUS, top_edge=True)
    for outside, prefix in ((t.BG, ""), (t.SURFACE, "card_")):
        rounded(f"{prefix}field", t.SURFACE_2, outside, RADIUS, border=t.BORDER_CONTROL)
        rounded(f"{prefix}field_focus", t.SURFACE_2, outside, RADIUS, border=t.ACCENT)
        rounded(f"{prefix}field_disabled", t.SURFACE, outside, RADIUS, border=t.SURFACE_2)
    rounded("card", t.SURFACE, t.BG, CARD_RADIUS, top_edge=True)
    rounded("group", t.SURFACE_2, t.SURFACE, RADIUS)
    rounded("pill", t.SURFACE_2, t.BG, RADIUS)
    rounded("tab", t.SURFACE_2, t.BG, RADIUS, top_only=True)
    rounded("tab_active", t.SURFACE_3, t.BG, RADIUS, top_only=True)
    rounded("tab_selected", t.SURFACE, t.BG, RADIUS, top_only=True, stripe=t.ACCENT)
    scrollbar_thumb("scrollbar_thumb", t.SURFACE_3)
    scrollbar_thumb("scrollbar_thumb_hover", t.BORDER_CONTROL)
    scale_track()
    scale_thumb("scale_thumb", t.ACCENT)
    scale_thumb("scale_thumb_hover", t.ACCENT_HOVER)
    print(f"wrote {len(list(OUT.glob('*.png')))} images to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
