"""Build the world map of the «Карта» tab (Atreia -> region -> zone) from the game's own world map, as the game draws it.

Sources (nothing is drawn here):
  * the client's sprite table  client_extract/raw/Data/ui/preload/preload/map.txt.xml   (skin -> texture, rectangle)
  * the client's map window    client_extract/raw/Data/ui/game/game/new_map_dialog.txt.xml (widget -> frame, skin)
  * the client's textures      client_extract/atlases/*.png
The globe is the game's mini globe (Asmodae and Elysea lands, the Abyss and the two rims of Balaurea, «внешние земли»),
each region is its 590 px map with a highlight sprite per zone. The pictures are enlarged with the portable Waifu2x
(downloads/icon_upscale, as tools/upscale_icons.py); without it they are written at their native size.

Writes data/maps/world/*.png and data/maps/world/world.json:
  {"globe": {"size": [w, h], "parts": [{"region", "frame": [x, y, w, h], "up", "over"}]},
   "regions": {region: {"title", "image", "size": 590, "zones": [{"code", "map_id", "layer", "frame", "highlight", "label"}]}}}
Frames are in the client's own pixels (the globe: its 173x196 box; a region: 590x590), the pictures are `scale` times larger.
Dev tool (needs Pillow). Usage: python tools/build_world_map.py
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
EXTRACT = ROOT / "client_extract"
ATLASES = EXTRACT / "atlases"
PRELOAD = EXTRACT / "raw" / "Data" / "ui" / "preload" / "preload" / "map.txt.xml"
DIALOG = EXTRACT / "raw" / "Data" / "ui" / "game" / "game" / "new_map_dialog.txt.xml"
OUT = ROOT / "data" / "maps" / "world"
MAPS = ROOT / "data" / "maps" / "maps.json"
WAIFU_PACKAGE = ROOT / "downloads" / "icon_upscale" / "waifu2x-ncnn-vulkan-20250915-windows"

GLOBE_SCALE = 4  # the mini globe is 173x196 in the client: four times for the start screen
REGION_SCALE = 2  # a region is 590x590: twice for a sharp picture on a large window
REGIONS = {  # client region -> its title and the globe buttons that open it
    "dark": ("Асмодея", ["dark"]),
    "light": ("Элиос", ["light"]),
    "abyss": ("Бездна", ["abyss"]),
    "dragon": ("Балаурея", ["dragon1", "dragon2"]),
}
ABYSS_LAYERS = {"ab1_1": 1, "ab1_2": 2, "ab1_3": 3}  # the Abyss zones of the client are the layers of Reshanta


def attrs(tag: str) -> dict[str, str]:
    return dict(re.findall(r'(\w+)="([^"]*)"', tag))


def numbers(text: str) -> list[int]:
    return [int(v) for v in text.split(",")]


def skins() -> dict[str, tuple[str, list[int]]]:
    """Skin name -> (texture file, [x, y, w, h])."""
    out = {}
    for tag in re.findall(r"<Skin [^>]*>", PRELOAD.read_text(encoding="utf-8")):
        a = attrs(tag)
        if "src_image" in a and "texture" in a:
            out[a["name"]] = (a["texture"].split("/")[-1].lower() + ".png", numbers(a["src_image"]))
    return out


def widgets() -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """Named widget -> frame, and skin -> frame of the image widget that shows it (zone names, highlights)."""
    text = DIALOG.read_text(encoding="utf-8", errors="replace")
    named = {a["name"]: numbers(a["frame"]) for a in map(attrs, re.findall(r"<Widget [^>]*>", text)) if "name" in a and "frame" in a}
    by_skin = {}
    for frame, skin in re.findall(r'<Widget [^>]*frame="([^"]*)"[^>]*><Skin name="([^"]*)"', text):
        by_skin.setdefault(skin, numbers(frame))
    return named, by_skin


def cut(texture: str, rect: list[int]) -> Image.Image:
    x, y, w, h = rect
    with Image.open(ATLASES / texture) as atlas:
        return atlas.convert("RGBA").crop((x, y, x + w, y + h))


def enlarge(image: Image.Image, scale: int, tmp: Path) -> Image.Image:
    """Waifu2x when it is there (as the map icons), else Lanczos; the alpha channel is scaled apart."""
    exe = next(WAIFU_PACKAGE.rglob("waifu2x-ncnn-vulkan.exe"), None) if WAIFU_PACKAGE.exists() else None
    size = (image.width * scale, image.height * scale)
    alpha = image.getchannel("A").resize(size, Image.Resampling.LANCZOS)
    if exe is None:
        rgb = image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    else:
        source, target = tmp / "in.png", tmp / "out.png"
        image.convert("RGB").save(source)
        subprocess.run([str(exe), "-i", str(source), "-o", str(target), "-n", "1", "-s", str(scale),
                        "-m", str(exe.parent / "models-cunet")], check=True, capture_output=True)
        with Image.open(target) as result:
            rgb = result.convert("RGB").resize(size)
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def zone_maps() -> dict[str, str]:
    """Client map code (the picture's name: df1, lf1a, lc1 …) -> map id."""
    index = json.loads(MAPS.read_text(encoding="utf-8"))
    out = {}
    for map_id, info in index.items():
        code = Path(info["file"]).stem.replace("_radar", "")
        out.setdefault(code, map_id)
    return out


def main() -> None:
    sk = skins()
    named, by_skin = widgets()
    codes = zone_maps()
    OUT.mkdir(parents=True, exist_ok=True)
    data: dict = {"globe": {"size": named["mini_world_map"][2:], "scale": GLOBE_SCALE, "parts": []}, "regions": {}}
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        # the globe: each part in its «up» and «over» look (Balaurea's two rims are drawn under the lands)
        box_x = named["mini_world_map"][0]
        for region, (_title, parts) in REGIONS.items():
            for part in parts:
                frame = named[f"mini_region_{part}"]
                files = {}
                for state in ("up", "over"):
                    texture, rect = sk[f"new_map_mini_world_{part}_{state}"]
                    name = f"globe_{part}_{state}.png"
                    enlarge(cut(texture, rect), GLOBE_SCALE, tmp).save(OUT / name)
                    files[state] = name
                data["globe"]["parts"].append({"region": region, "part": part, "frame": [frame[0] - box_x, *frame[1:]], **files})
        order = {"dragon2": 0, "dragon1": 1, "dark": 2, "light": 3, "abyss": 4}
        data["globe"]["parts"].sort(key=lambda p: order[p["part"]])
        # the regions: the map and, per zone, its highlight and where the game writes its name
        for region, (title, _parts) in REGIONS.items():
            texture, rect = sk[f"new_map_region_{region}"]
            image = f"region_{region}.jpg"
            enlarge(cut(texture, rect), REGION_SCALE, tmp).convert("RGB").save(OUT / image, quality=90)
            zones = []
            prefix = "zone_"
            container = re.search(rf'name="region_{region}_container".*?(?=name="region_\w+_container"|name="zone_title")',
                                  DIALOG.read_text(encoding="utf-8", errors="replace"), re.S)
            for code in re.findall(r'name="zone_(\w+)" type="button"', container.group(0) if container else ""):
                highlight_texture, highlight_rect = sk[f"new_map_highlight_zone_{code}"]
                highlight = f"zone_{code}.png"
                enlarge(cut(highlight_texture, highlight_rect), REGION_SCALE, tmp).save(OUT / highlight)
                map_id = codes.get(code) or (codes.get("ab1_1") if code in ABYSS_LAYERS else None)
                zones.append({
                    "code": code, "map_id": map_id, "layer": ABYSS_LAYERS.get(code),
                    "frame": named[f"{prefix}{code}"],  # the button: where a click opens the zone
                    "highlight": by_skin.get(f"new_map_highlight_zone_{code}"), "highlight_file": highlight,
                    "label": by_skin.get(f"map_zone_text_{code}"),  # where the game writes the zone's name
                })
            data["regions"][region] = {"title": title, "image": image, "size": rect[2], "scale": REGION_SCALE, "zones": zones}
    (OUT / "world.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"world map: {sum(len(r['zones']) for r in data['regions'].values())} zones in {len(data['regions'])} regions -> {OUT}")


if __name__ == "__main__":
    main()
