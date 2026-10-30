"""Build the world map of the «Карта» tab (Atreia -> region -> zone) from the game's own world map, as the game draws it.

Sources (nothing is drawn here):
  * the client's sprite table  client_extract/raw/Data/ui/preload/preload/map.txt.xml   (skin -> texture, rectangle)
  * the client's map window    client_extract/raw/Data/ui/game/game/new_map_dialog.txt.xml (widget -> frame, skin)
  * the client's textures      client_extract/atlases/*.png
The globe is the game's mini globe (Asmodae and Elysea lands, the Abyss and the two rims of Balaurea, «внешние земли»).
Asmodae, Elysea and Balaurea use the game's coloured region maps (768x608, worldmap_dark/light/dragon). Their zone
highlights have no layout in the client: each highlight is found on its map by normalised cross-correlation, named by
the zone whose place in the newer 590 px layout (new_map_dialog) fits best; the sprite is already cut to its zone; the newer layout's buttons and name places are carried over by the same fit. The Abyss keeps its
590 px map and layout. The pictures are enlarged with the portable Waifu2x (downloads/icon_upscale, as
tools/upscale_icons.py); without it with Lanczos.

Writes data/maps/world/*.png|jpg and data/maps/world/world.json:
  {"globe": {"size": [w, h], "scale", "parts": [{"region", "part", "frame": [x, y, w, h], "up", "over"}]},
   "regions": {region: {"title", "image", "size": [w, h], "scale",
                        "zones": [{"code", "map_id", "layer", "frame", "highlight", "highlight_file", "label"}]}}}
Frames are in the client's own pixels (the globe: its 173x196 box; a region: its map), the pictures are `scale` times larger.
Dev tool (needs Pillow and numpy). Usage: python tools/build_world_map.py
"""

from __future__ import annotations

import itertools
import json
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
EXTRACT = ROOT / "client_extract"
ATLASES = EXTRACT / "atlases"
PRELOAD = EXTRACT / "raw" / "Data" / "ui" / "preload" / "preload" / "map.txt.xml"
DIALOG = EXTRACT / "raw" / "Data" / "ui" / "game" / "game" / "new_map_dialog.txt.xml"
OUT = ROOT / "data" / "maps" / "world"
MAPS = ROOT / "data" / "maps" / "maps.json"
WAIFU_PACKAGE = ROOT / "downloads" / "icon_upscale" / "waifu2x-ncnn-vulkan-20250915-windows"

GLOBE_SCALE = 4  # the mini globe is 173x196 in the client: four times, shown at most 2.6 times (sharp)
REGION_SCALE = 2  # twice for a sharp picture on a large window
OLD_REGIONS = {"dark", "light", "dragon"}  # the coloured 768x608 maps (worldmap_<region>.png)
OLD_SIZE = (768, 608)
REGIONS = {  # client region -> its title and the globe buttons that open it
    "dark": ("Асмодея", ["dark"]),
    "light": ("Элиос", ["light"]),
    "abyss": ("Бездна", ["abyss"]),
    "dragon": ("Внешние земли", ["dragon1", "dragon2"]),
}
ICONS = {"underpass": [776, 81, 29, 30]}  # zones the coloured maps have no highlight for: their marker in the same atlas
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
    image = image.convert("RGBA")
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


def components(alpha: np.ndarray, min_px: int = 40) -> list[tuple[int, int, int, int]]:
    """Boxes [x, y, w, h] of the opaque pieces of an atlas (at half resolution: the pieces are far apart)."""
    small = alpha[::2, ::2]
    h, w = small.shape
    seen = np.zeros_like(small, bool)
    boxes = []
    for y in range(h):
        for x in np.where(small[y] & ~seen[y])[0]:
            if seen[y, x]:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            y0 = y1 = y
            x0 = x1 = x
            while stack:
                cy, cx = stack.pop()
                y0, y1, x0, x1 = min(y0, cy), max(y1, cy), min(x0, cx), max(x1, cx)
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and small[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            if (x1 - x0) * 2 >= min_px and (y1 - y0) * 2 >= min_px:
                boxes.append((int(x0) * 2, int(y0) * 2, (int(x1) - int(x0) + 1) * 2, (int(y1) - int(y0) + 1) * 2))
    return boxes


def find(image: np.ndarray, templ: np.ndarray) -> tuple[int, int, float]:
    """Where a template sits in an image (grey levels): normalised cross-correlation through the FFT."""
    H, W = image.shape
    h, w = templ.shape
    t = templ - templ.mean()
    corr = np.fft.irfft2(np.fft.rfft2(image) * np.fft.rfft2(t[::-1, ::-1], s=(H, W)), s=(H, W))[h - 1:, w - 1:]

    def window(a: np.ndarray) -> np.ndarray:
        s = np.pad(a.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        return s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]

    s1, s2 = window(image), window(image * image)
    score = corr / (np.sqrt(np.maximum(s2 - s1 * s1 / (h * w), 1e-6)) * np.sqrt((t * t).sum()))
    y, x = np.unravel_index(np.argmax(score), score.shape)
    return int(x), int(y), float(score[y, x])


def fit_axes(src: np.ndarray, dst: np.ndarray) -> tuple[list[float], float]:
    """dst ≈ src * k + b per axis (least squares): [kx, bx, ky, by] and the mean error."""
    params: list[float] = []
    error = 0.0
    for axis in (0, 1):
        a = np.stack([src[:, axis], np.ones(len(src))], 1)
        sol, *_ = np.linalg.lstsq(a, dst[:, axis], rcond=None)
        params += [float(v) for v in sol]
        error += float(np.abs(a @ sol - dst[:, axis]).mean())
    return params, error


def old_region(region: str, zones: list[dict]) -> tuple[Image.Image, dict[str, tuple[Image.Image, list[int]]], list[float]]:
    """The coloured map of a region; per zone code its highlight (cut to the zone's shape) and box on the map; and the
    fit from the 590 px layout to this map ([kx, bx, ky, by])."""
    with Image.open(ATLASES / f"worldmap_{region}.png") as atlas:
        rgba = np.array(atlas.convert("RGBA")).astype(float)
    w, h = OLD_SIZE
    base = rgba[:h, :w, :3]
    alpha = rgba[:, :, 3] > 10
    alpha[: h + 4, : w + 4] = False
    grey = base.mean(2)
    found = []
    for x, y, cw, ch in components(alpha):
        crop = rgba[y:y + ch, x:x + cw]
        ys, xs = np.where(crop[:, :, 3] > 10)
        crop = crop[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        px, py, score = find(grey, crop[:, :, :3].mean(2))
        if score > 0.5:
            found.append((crop, [px, py, crop.shape[1], crop.shape[0]]))
    targets = [z for z in zones if z.get("highlight")]
    new_centres = np.array([[r[0] + r[2] / 2, r[1] + r[3] / 2] for r in (z["highlight"] for z in targets)])
    old_centres = np.array([[b[0] + b[2] / 2, b[1] + b[3] / 2] for _crop, b in found])
    best = None
    for chosen in itertools.permutations(range(len(targets)), len(found)):
        params, error = fit_axes(new_centres[list(chosen)], old_centres)
        if params[0] <= 0 or params[2] <= 0:  # the maps are not mirrored
            continue
        if best is None or error < best[0]:
            best = (error, chosen, params)
    _error, chosen, params = best
    lights = {}
    for (crop, box), index in zip(found, chosen):
        x, y, cw, ch = box
        piece = Image.fromarray(crop.astype(np.uint8), "RGBA")  # the game cut it to the zone already (its alpha)
        lights[targets[index]["code"]] = (piece, box)
    return Image.fromarray(base.astype(np.uint8), "RGB"), lights, params


def zone_maps() -> dict[str, str]:
    """Client map code (the picture's name: df1, lf1a, lc1 …) -> map id."""
    index = json.loads(MAPS.read_text(encoding="utf-8"))
    out = {}
    for map_id, info in index.items():
        out.setdefault(Path(info["file"]).stem.replace("_radar", ""), map_id)
    return out


def main() -> None:
    sk = skins()
    named, by_skin = widgets()
    codes = zone_maps()
    text = DIALOG.read_text(encoding="utf-8", errors="replace")
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("zone_*.png"):
        old.unlink()
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
        # the regions: the map and, per zone, its highlight, where a click opens it and where its name is written
        for region, (title, _parts) in REGIONS.items():
            container = re.search(rf'name="region_{region}_container".*?(?=name="region_\w+_container"|name="zone_title")', text, re.S)
            zones = []
            for code in re.findall(r'name="zone_(\w+)" type="button"', container.group(0) if container else ""):
                map_id = codes.get(code) or (codes.get("ab1_1") if code in ABYSS_LAYERS else None)
                zones.append({"code": code, "map_id": map_id, "layer": ABYSS_LAYERS.get(code), "frame": named[f"zone_{code}"],
                              "highlight": by_skin.get(f"new_map_highlight_zone_{code}"), "highlight_file": "",
                              "label": by_skin.get(f"map_zone_text_{code}")})
            image = f"region_{region}.jpg"
            if region in OLD_REGIONS:
                picture, lights, (kx, bx, ky, by) = old_region(region, zones)

                def move(r: list[int] | None) -> list[int] | None:
                    return [round(r[0] * kx + bx), round(r[1] * ky + by), round(r[2] * kx), round(r[3] * ky)] if r else None

                for zone in zones:
                    zone["frame"], zone["label"] = move(zone["frame"]), move(zone["label"])
                    if zone["code"] in lights:
                        piece, box = lights[zone["code"]]
                        zone["highlight"], zone["highlight_file"] = box, f"zone_{zone['code']}.png"
                        enlarge(piece, REGION_SCALE, tmp).save(OUT / zone["highlight_file"])
                    else:  # no coloured highlight (the Silentera tunnel): the game's swirl marks it, its box opens it
                        zone["highlight"] = None
                        if zone["code"] in ICONS:
                            zone["icon"] = f"zone_{zone['code']}_icon.png"
                            enlarge(cut(f"worldmap_{region}.png", ICONS[zone["code"]]), GLOBE_SCALE, tmp).save(OUT / zone["icon"])
                size = list(OLD_SIZE)
            else:
                texture, rect = sk[f"new_map_region_{region}"]
                picture = cut(texture, rect)
                for zone in zones:
                    highlight_texture, highlight_rect = sk[f"new_map_highlight_zone_{zone['code']}"]
                    zone["highlight_file"] = f"zone_{zone['code']}.png"
                    enlarge(cut(highlight_texture, highlight_rect), REGION_SCALE, tmp).save(OUT / zone["highlight_file"])
                size = [rect[2], rect[3]]
            enlarge(picture, REGION_SCALE, tmp).convert("RGB").save(OUT / image, quality=92)
            data["regions"][region] = {"title": title, "image": image, "size": size, "scale": REGION_SCALE, "zones": zones}
    (OUT / "world.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"world map: {sum(len(r['zones']) for r in data['regions'].values())} zones in {len(data['regions'])} regions -> {OUT}")


if __name__ == "__main__":
    main()
