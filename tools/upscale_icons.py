"""Create repeatable 4x map icon enlargements and a visual comparison sheet.

Requires Pillow. Reads data/maps/icons and writes only to client_extract/icons_hd
and docs/icons-compare.png. Method A is Scale2x applied twice; method B is
Lanczos with premultiplied alpha. The main output PNGs use method A as a
temporary default until the user chooses a method for integration.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "data" / "maps" / "icons"
OUTPUT_DIR = ROOT / "client_extract" / "icons_hd"
COMPARE_PATH = ROOT / "docs" / "icons-compare.png"

# Provenance for the current data/maps/icons assets. Client entries point to
# the sprite definition or extracted client image; aiondb entries name the
# existing downloaded source used by build_map_icons.py.
SOURCES = {
    "teleport": ("client sprite v4_common:v4_radar_icon_teleport", "16x16"),
    "warehouse": ("client sprite v4_common:v4_radar_icon_warehouse", "16x16"),
    "merchant": ("client sprite v4_common:v4_radar_icon_merchant", "16x16"),
    "coin_merchant": ("client sprite v4_common:coin_merchant_marker", "16x16"),
    "vendor": ("client sprite v4_common:v4_radar_icon_vendor", "16x16"),
    "stigma": ("client sprite v4_common:v4_radar_icon_stigma_master", "16x16"),
    "postbox": ("client sprite v4_common:v4_radar_postbox_icon", "16x16"),
    "bindstone": ("client sprite v4_common:v4_radar_bindstone_icon", "16x16"),
    "quest_point": ("client sprite v4_common:v4_radar_quest_icon_zonemap", "18x18"),
    "quest_give": ("client sprite v4_common:v4_radar_quest_give_icon_zonemap", "18x18"),
    "quest_important": ("client sprite v4_common:v4_radar_important_quest_give_icon_zonemap", "18x18"),
    "quest_event": ("client sprite v4_common:v4_radar_event_quest_give_icon_zonemap", "18x18"),
    "artifact": ("client image client_extract/icons/abyss_artifact.png", "34x32"),
    "fortress": ("client image client_extract/icons/abyss_fortress.png", "34x32"),
    "dungeon": ("client image client_extract/icons/abyss_indun.png", "36x29"),
    "raid_boss": ("client image client_extract/icons/abyss_bossraid_dark.png", "30x34"),
    "portal": ("client image client_extract/icons/abyss_underpass.png", "30x30"),
    "direct_portal": ("client image client_extract/icons/teleport_dest_up.png", "32x78"),
    "camp": ("aiondb icon downloads/aiondb_icons map_icon_ui_camp", "36x36"),
}


def scale2x(image: Image.Image) -> Image.Image:
    """Classic Scale2x edge-preserving pixel-art enlargement."""
    src = image.convert("RGBA")
    w, h = src.size
    pixels = src.load()
    out = Image.new("RGBA", (w * 2, h * 2))
    dst = out.load()
    for y in range(h):
        for x in range(w):
            e = pixels[x, y]
            b = pixels[x, y - 1] if y > 0 else e
            d = pixels[x - 1, y] if x > 0 else e
            f = pixels[x + 1, y] if x + 1 < w else e
            hpx = pixels[x, y + 1] if y + 1 < h else e
            if b != hpx and d != f:
                e0 = d if d == b else e
                e1 = f if b == f else e
                e2 = d if d == hpx else e
                e3 = f if hpx == f else e
            else:
                e0 = e1 = e2 = e3 = e
            dst[2 * x, 2 * y] = e0
            dst[2 * x + 1, 2 * y] = e1
            dst[2 * x, 2 * y + 1] = e2
            dst[2 * x + 1, 2 * y + 1] = e3
    return out


def enlarge_scale2x(image: Image.Image) -> Image.Image:
    return scale2x(scale2x(image))


def enlarge_lanczos(image: Image.Image) -> Image.Image:
    # Premultiply first so RGB values in transparent pixels cannot create halos.
    premultiplied = image.convert("RGBA").convert("RGBa")
    return premultiplied.resize((image.width * 4, image.height * 4), Image.Resampling.LANCZOS).convert("RGBA")


def fit_center(image: Image.Image, size: int) -> Image.Image:
    fitted = image.copy()
    fitted.thumbnail((size - 8, size - 8), Image.Resampling.LANCZOS)
    return fitted


def create_comparison(entries: list[tuple[str, Image.Image, Image.Image, Image.Image]]) -> None:
    columns = [
        (48, "Source @ 48px"), (48, "Scale2x x2 @ 48px"), (48, "Lanczos x4 @ 48px"),
        (80, "Source @ 80px"), (80, "Scale2x x2 @ 80px"), (80, "Lanczos x4 @ 80px"),
    ]
    left, cell_w, header_h, row_h = 148, 134, 72, 112
    width = left + cell_w * len(columns)
    height = header_h + row_h * len(entries) + 28
    sheet = Image.new("RGB", (width, height), (19, 24, 29))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((18, 18), "MAP ICON UPSCALE COMPARISON", font=font, fill=(235, 239, 243))
    for index, (box, label) in enumerate(columns):
        x = left + index * cell_w
        draw.text((x + 8, 42), label, font=font, fill=(170, 191, 207))
    for row, (name, source, method_a, method_b) in enumerate(entries):
        y = header_h + row * row_h
        draw.text((18, y + 8), name, font=font, fill=(225, 230, 235))
        variants = (source, method_a, method_b, source, method_a, method_b)
        for col, ((box_size, _), image) in enumerate(zip(columns, variants)):
            x = left + col * cell_w
            draw.rounded_rectangle((x + 16, y + 7, x + cell_w - 16, y + 7 + 88), radius=5, fill=(30, 38, 45))
            thumb = fit_center(image, box_size)
            tx = x + (cell_w - thumb.width) // 2
            ty = y + 7 + (88 - thumb.height) // 2
            sheet.paste(thumb, (tx, ty), thumb)
        draw.line((12, y + row_h - 1, width - 12, y + row_h - 1), fill=(48, 59, 67), width=1)
    COMPARE_PATH.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(COMPARE_PATH, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=("scale2x", "lanczos"), default="scale2x",
                        help="upscaler used for client_extract/icons_hd/<type>.png (default: scale2x)")
    args = parser.parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    icon_files = sorted(SOURCE_DIR.glob("*.png"))
    unknown = [path.stem for path in icon_files if path.stem not in SOURCES]
    missing = sorted(set(SOURCES) - {path.stem for path in icon_files})
    if unknown or missing:
        raise SystemExit(f"Source list mismatch; unknown={unknown}, missing={missing}")

    rows = ["type\tsource\tsource_size\toutput_size\tmethod"]
    compare_entries = []
    for path in icon_files:
        with Image.open(path) as opened:
            source = opened.convert("RGBA")
        method_a = enlarge_scale2x(source)
        method_b = enlarge_lanczos(source)
        selected = method_a if args.method == "scale2x" else method_b
        selected.save(OUTPUT_DIR / path.name, optimize=True)
        source_name, documented_size = SOURCES[path.stem]
        if f"{source.width}x{source.height}" != documented_size:
            raise SystemExit(f"Unexpected source dimensions for {path.name}: {source.size} != {documented_size}")
        rows.append(f"{path.stem}\t{source_name}\t{source.width}x{source.height}\t{selected.width}x{selected.height}\t{args.method} x4")
        compare_entries.append((path.stem, source, method_a, method_b))

    (OUTPUT_DIR / "SOURCES.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    create_comparison(compare_entries)
    print(f"Created {len(icon_files)} icons in {OUTPUT_DIR}")
    print(f"Created comparison sheet {COMPARE_PATH}")


if __name__ == "__main__":
    main()
