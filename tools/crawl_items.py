"""Download item pages from kb.aionempire.com and keep the parsed spec and icon name.

Input: a TSV `id<TAB>grade<TAB>level<TAB>name` (the full site list, see tools/kb_crawl.py),
filtered by PREFIXES; or `...<TAB>type` from tools/list_by_type.py, taken as is.
Output: a JSON-lines cache, one {"id", "grade", "level", "name", "type", "icon", "spec"} per item.
Items already in the cache are skipped, so the crawl can be resumed.
Dev tool. Usage: python tools/crawl_items.py <all_items.tsv> <cache.jsonl> [min_level]
"""

import concurrent.futures as cf
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.items.specs import parse_spec  # noqa: E402

SITE = "https://kb.aionempire.com"
HEADERS = {"User-Agent": "Mozilla/5.0", "Cookie": "PLAY_LANG=ru"}
# 100/101 weapons, 110-114 body armour, 115 shields, 187 wings
PREFIXES = ("100", "101", "110", "111", "112", "113", "114", "115", "187")
# min_level does not apply to these (not in the search list, only chat links and tooltips)
ALL_LEVEL_TYPES = {
    "production", "recipes", "supplies", "food", "potions", "magic-items", "magic-stones",
    "ench-stones", "god-stones", "dyes", "titles", "skillbooks", "other",
}
ICON_RE = re.compile(r'og:image" content="[^"]*?/assets/images/icons/([^"]+)"')


def fetch_item(row: tuple[str, ...]) -> dict | None:
    item_id, grade, level, name = row[:4]
    site_type = row[4] if len(row) > 4 else ""
    for attempt in range(4):
        try:
            request = urllib.request.Request(f"{SITE}/items/{item_id}", headers=HEADERS)
            with urllib.request.urlopen(request, timeout=30) as response:
                page = response.read().decode("utf-8", "replace")
            icon = ICON_RE.search(page)
            return {
                "id": item_id,
                "grade": grade,
                "level": int(level),
                "name": name,
                "type": site_type,
                "icon": icon.group(1).lower() if icon else "",
                "spec": parse_spec(page),
            }
        except Exception as exc:  # retry transient errors
            error = exc
            time.sleep(2 * (attempt + 1))
    print(f"{item_id} failed: {error}", file=sys.stderr)
    return None


def main() -> int:
    source, cache = Path(sys.argv[1]), Path(sys.argv[2])
    min_level = int(sys.argv[3]) if len(sys.argv) > 3 else 45
    done: set[str] = set()
    if cache.exists():
        with open(cache, encoding="utf-8") as f:
            done = {json.loads(line)["id"] for line in f if line.strip()}
    rows = []
    with open(source, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 4:
                wanted = parts[0][:3] in PREFIXES and int(parts[2]) >= min_level
            elif len(parts) == 5:
                wanted = parts[4] in ALL_LEVEL_TYPES or int(parts[2]) >= min_level
            else:
                continue
            if wanted and parts[0] not in done and parts[1] != "junk":
                rows.append(tuple(parts))
    print(f"{len(done)} cached, {len(rows)} to fetch", flush=True)
    with open(cache, "a", encoding="utf-8") as out, cf.ThreadPoolExecutor(6) as pool:
        for n, item in enumerate(pool.map(fetch_item, rows), 1):
            if item is not None:
                out.write(json.dumps(item, ensure_ascii=False) + "\n")
            if n % 250 == 0:
                out.flush()
                print(f"{n}/{len(rows)}", flush=True)
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
