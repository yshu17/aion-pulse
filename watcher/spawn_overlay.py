"""Geometry and rendering for one approximate spawn-area circle; no Tk state."""
from __future__ import annotations

import math


def enclosing_spawn_circle(polygons) -> tuple[float, float, float] | None:
    """Merge all selected groups in one zone into a circle covering their points."""
    points = [(float(x), float(y)) for polygon in polygons for x, y in polygon]
    if not points:
        return None
    cx = (min(x for x, _ in points) + max(x for x, _ in points)) / 2
    cy = (min(y for _, y in points) + max(y for _, y in points)) / 2
    radius = max(24.0, max(math.hypot(x-cx, y-cy) for x, y in points) + 12)
    return cx, cy, radius


def paint_spawn_circle(image, center: tuple[float, float], radius: float):
    """Blue translucent fill with a soft edge, composited beneath labels and pins."""
    from PIL import Image, ImageDraw, ImageFilter
    cx, cy = center
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=92, outline=150, width=2)
    mask = mask.filter(ImageFilter.GaussianBlur(max(2, min(24, radius * 0.08))))
    layer = Image.new("RGBA", image.size, (78, 138, 196, 0))
    layer.putalpha(mask)
    return Image.alpha_composite(image.convert("RGBA"), layer).convert("RGB")
