"""Rendering of one approximate spawn-area circle (the geometry is core.map.zones.enclosing_spawn_circle)."""
from __future__ import annotations

from core.map.zones import enclosing_spawn_circle  # noqa: F401  (kept importable from here)


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
