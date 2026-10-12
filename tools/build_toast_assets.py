"""SN-3: crop existing client sprites and prepare toast assets; no downloads.

Run from the project: python tools/build_toast_assets.py
Native crops/provenance go to client_extract/raw/toast_assets, runtime files
to data/ui/toasts. Waifu2x is the existing project-local package.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_map_icons import sprite_table, cut_sprite
from upscale_icons import enlarge_waifu2x

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "client_extract/raw/toast_assets"
OUT = ROOT / "data/ui/toasts"
SPRITES = {
    "reset": "v4_refresh_up@v4_common",
    "chat": "v5_chat_menu_up@v5_common_1",
    "warning": "v5_item_attr_reduced_warning@v5_common_1",
    "event": "v4_radar_event_quest_give_icon_zonemap@v4_common",
}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    tables = (ROOT / "client_extract/raw/Data/ui/preload/preload").glob("*.xml")
    sprites = sprite_table([p.read_text(encoding="utf-8", errors="replace") for p in tables])
    provenance = {}
    temp_root = ROOT / "tmp"
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="toast_assets_", dir=temp_root) as name:
        for kind, sprite in SPRITES.items():
            native = RAW / f"{kind}.png"
            cut_sprite(sprite, sprites, native)
            hd = enlarge_waifu2x(native, Path(name) / f"{kind}.png")
            hd.save(RAW / f"{kind}_hd.png")
            install_icon(kind, hd)
            provenance[kind] = {"sprite": sprite, "method": "Waifu2x noise=1 x4"}
    # This fortress was already extracted and upscaled for the map.
    install_icon("siege", Image.open(ROOT / "client_extract/icons_hd/fortress.png").convert("RGBA"))
    provenance["siege"] = {"source": "client_extract/icons_hd/fortress.png", "original": "client_extract/icons/abyss_fortress.png", "method": "existing Waifu2x x4"}
    # Contiguous 9-slice rectangle defined by v4_tooltip in version4.txt.xml.
    atlas = ROOT / "client_extract/raw/textures/ui/ui/v4_common.png"
    with Image.open(atlas) as image:
        frame = image.convert("RGBA").crop((210, 212, 244, 247))
    frame.save(RAW / "frame.png")
    frame.save(OUT / "frame.png")
    frame.resize((68, 70), Image.Resampling.LANCZOS).save(OUT / "frame@2x.png")
    provenance["frame"] = {"source": str(atlas.relative_to(ROOT)).replace("\\", "/"), "sprite": "v4_tooltip", "rect": [210, 212, 34, 35], "borders": [9, 10, 13, 11], "method": "native nine-slice, @2x Lanczos"}
    (OUT / "sources.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    sheet = Image.new("RGB", (640, 150), "#1c1e24")
    draw = ImageDraw.Draw(sheet)
    for i, kind in enumerate([*SPRITES, "siege"]):
        icon = Image.open(OUT / f"{kind}@2x.png").convert("RGBA")
        sheet.paste(icon, (i * 125 + 24, 12), icon)
        draw.text((i * 125 + 24, 100), kind, fill="white")
    sheet.save(ROOT / "docs/toast-assets.png")
    print(f"Prepared 5 client icons and 9-slice frame in {OUT}")


def install_icon(kind: str, hd: Image.Image) -> None:
    if hd.convert("RGBA").getchannel("A").getbbox() is None:
        raise ValueError(f"Empty client sprite: {kind}")
    for scale, suffix in [(1, ""), (1.25, "@125"), (1.5, "@150"), (2, "@2x")]:
        size = round(36 * scale)
        fitted = hd.convert("RGBa")
        fitted.thumbnail((size, size), Image.Resampling.LANCZOS)
        fitted = fitted.convert("RGBA")
        canvas = Image.new("RGBA", (size, size))
        canvas.alpha_composite(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
        canvas.save(OUT / f"{kind}{suffix}.png")


if __name__ == "__main__":
    main()
