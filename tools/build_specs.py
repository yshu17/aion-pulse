"""Download kb.aionempire.com pages for data/watch_items.csv and write data/item_specs.json.

Dev tool: run once when the watch list changes. Usage: python tools/build_specs.py
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from watcher.catalog import load_watch_items  # noqa: E402
from watcher.specs import parse_spec  # noqa: E402

URL = "https://kb.aionempire.com/items/{}"
HEADERS = {"User-Agent": "Mozilla/5.0", "Cookie": "PLAY_LANG=ru"}


def main() -> int:
    data = ROOT / "data"
    specs = {}
    for item in load_watch_items(data / "watch_items.csv"):
        request = urllib.request.Request(URL.format(item.id), headers=HEADERS)
        with urllib.request.urlopen(request, timeout=30) as response:
            page = response.read().decode("utf-8", "replace")
        specs[item.id] = parse_spec(page)
        print(item.id, item.name, len(specs[item.id]["blocks"]), "blocks")
        time.sleep(0.2)
    out = data / "item_specs.json"
    out.write_text(json.dumps(specs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(specs)} specs -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
