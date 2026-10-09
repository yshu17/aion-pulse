"""Download reference zone maps from aioncodex.com into data/maps/external/.

The active map tab uses the local-client rasters in data/maps/client/ and maps.json. This optional
reference downloader writes maps_external.json so it cannot replace the app's active map index.

aioncodex shows each zone as a 4096 px Leaflet map (TMS tiles /zonemap/<code>/{z}/{x}/{y}.jpg) and
places NPCs on it from their game coordinates. Fitting both for many NPCs gives, per zone,
    map_x = a * game_y + b,    map_y = c * game_x + d      (in 4096 px units)
— the image's horizontal axis is the game's y. The fitted values are in ZONES below.
Dev tool. Usage: python tools/fetch_maps.py [zoom]   (zoom 3 = 2048 px, the default)
"""

import io
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://aioncodex.com/zonemap"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "Referer": "https://aioncodex.com/"}
FULL = 4096
# code, map id, (a, b, c, d) fitted from aioncodex NPC spawns (see module docstring)
ZONES = [
    ("df4", "220070000", (1.3342, 0.0, 1.3342, 0.0)),  # Келькмарос
    ("lf4", "210050000", (1.3342, 0.0, 1.3342, 0.0)),  # Ингисон
    ("underpass", "600010000", (2.6598, 0.0, 2.6598, 0.0)),  # Тоннель Силентера
    ("dc1", "120010000", (3.9767, -3261.0, 3.9765, -2783.5)),  # Пандемониум
    ("df1", "220010000", (1.7809, -1335.7, 1.7809, 0.0)),  # Исхальген
    ("df1a", "220030000", (1.4731, -95.0, 1.4724, -808.7)),  # Альтгард
    ("df2", "220020000", (1.3342, 0.0, 1.3342, 0.0)),  # Морхейм
    ("df2a", "220050000", (1.3342, 0.0, 1.3340, 0.0)),  # Брустхонин
    ("df3", "220040000", (1.3342, 0.0, 1.3342, 0.0)),  # Белуслан
]


def stitch(code: str, zoom: int):
    from PIL import Image

    count = 2**zoom
    image = Image.new("RGB", (256 * count, 256 * count))
    for x in range(count):
        for y in range(count):
            url = f"{SITE}/{code}/{zoom}/{x}/{y}.jpg"
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
                tile = Image.open(io.BytesIO(r.read())).convert("RGB")
            image.paste(tile, (x * 256, (count - 1 - y) * 256))  # TMS: y counts from the bottom
    return image


def main() -> int:
    zoom = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    maps_dir = ROOT / "data" / "maps"
    out = maps_dir / "external"
    out.mkdir(parents=True, exist_ok=True)
    index = {}
    for code, map_id, (a, b, c, d) in ZONES:
        image = stitch(code, zoom)
        image.save(out / f"{code}.jpg", quality=85, optimize=True)
        scale = image.size[0] / FULL
        # pixel = coefficient * game + offset, already scaled to this image
        index[map_id] = {"file": f"external/{code}.jpg", "size": image.size[0],
                         "x": [a * scale, b * scale], "y": [c * scale, d * scale]}
        print(code, map_id, (out / f"{code}.jpg").stat().st_size // 1024, "KB", flush=True)
    (maps_dir / "maps_external.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
