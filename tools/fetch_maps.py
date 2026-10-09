"""Download zone maps from easyaionmaps.com (Leaflet tiles) and stitch them into one PNG per zone.

The map covers 48 x 48 Leaflet units; at zoom z a unit is 2**z px and tiles are 256 px,
named {z}/{x}_{y}.png. Output: <out_dir>/<zone>.png (256-colour PNG).
Dev tool (needs Pillow). Usage: python tools/fetch_maps.py <out_dir> [zoom] [zone ...]
"""

import concurrent.futures as cf
import io
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = "https://easyaionmaps.com/assets/maps"
HEADERS = {"User-Agent": "Mozilla/5.0"}
ZONES = [
    "gelkmaros", "inggison", "silentera_canyon", "abyss_low", "abyss_top", "abyss_core",
    "ishalgen", "altgard", "morheim", "brusthonin", "beluslan",
    "poeta", "verteron", "eltnen", "theobomos", "heiron",
]


def tile(zone: str, zoom: int, x: int, y: int):
    from PIL import Image

    url = f"{SITE}/{zone}/{zoom}/{x}_{y}.png"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
            return x, y, Image.open(io.BytesIO(r.read())).convert("RGB")
    except urllib.error.HTTPError:
        return x, y, None


def stitch(zone: str, zoom: int, out_dir: Path) -> Path:
    from PIL import Image

    count = 48 * 2**zoom // 256
    image = Image.new("RGB", (count * 256, count * 256), (20, 21, 25))
    jobs = [(zone, zoom, x, y) for x in range(count) for y in range(count)]
    with cf.ThreadPoolExecutor(6) as pool:
        for x, y, part in pool.map(lambda a: tile(*a), jobs):
            if part is not None:
                image.paste(part, (x * 256, y * 256))
    path = out_dir / f"{zone}.png"
    image.quantize(256, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)
    return path


def main() -> int:
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)
    zoom = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    for zone in sys.argv[3:] or ZONES:
        path = stitch(zone, zoom, out_dir)
        print(zone, path.stat().st_size // 1024, "KB", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
