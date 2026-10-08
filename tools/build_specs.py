"""Refresh data for the watch list from kb.aionempire.com.

For every row of data/watch_items.csv: download the item page, store its tooltip spec in
data/item_specs.json, fill the «category» column, and fetch the icon if it is missing.
Dev tool (needs Pillow for icons). Usage: python tools/build_specs.py
"""

import csv
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from watcher.catalog import category_for, load_watch_items  # noqa: E402
from watcher.specs import parse_spec  # noqa: E402

SITE = "https://kb.aionempire.com"
HEADERS = {"User-Agent": "Mozilla/5.0", "Cookie": "PLAY_LANG=ru"}
ICON_SIZE = 56
ICON_CONTENT = 40  # site icons are 64x64 sprites with the picture in the top-left 40x40


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def item_type(spec: dict) -> str:
    for block in spec["blocks"]:
        if block["kind"] == "pairs":
            for name, value in block["rows"]:
                if name == "Тип":
                    return value
    return ""


def save_icon(page: str, path: Path) -> None:
    from PIL import Image

    match = re.search(r'og:image" content="[^"]*?/assets/images/icons/([^"]+)"', page)
    if match is None:
        print(f"  no icon on page for {path.stem}")
        return
    try:
        raw = fetch(f"{SITE}/assets/images/icons/{match.group(1).lower()}")
    except urllib.error.HTTPError as exc:
        print(f"  icon for {path.stem} not available on the site ({exc.code}); app shows a placeholder")
        return
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    image = image.crop((0, 0, ICON_CONTENT, ICON_CONTENT)).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    image.save(path, optimize=True)


def main() -> int:
    data = ROOT / "data"
    specs, rows = {}, []
    for item in load_watch_items(data / "watch_items.csv"):
        page = fetch(f"{SITE}/items/{item.id}").decode("utf-8", "replace")
        spec = parse_spec(page)
        specs[item.id] = spec
        category = category_for(item_type(spec), item.name)
        rows.append([item.id, item.name, item.level, category])
        icon = data / "icons" / f"{item.id}.png"
        if not icon.exists():
            save_icon(page, icon)
        print(item.id, item.name, category, len(spec["blocks"]), "blocks")
        time.sleep(0.2)
    (data / "item_specs.json").write_text(json.dumps(specs, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(data / "watch_items.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["id", "name", "level", "category"])
        writer.writerows(rows)
    print(f"wrote {len(specs)} specs and categories")
    return 0


if __name__ == "__main__":
    sys.exit(main())
