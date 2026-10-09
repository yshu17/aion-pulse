"""List kb.aionempire.com items of given site types (the «?type=» filter of the item list).

Output TSV: id, grade, level, name, type — the input format of tools/crawl_items.py.
Dev tool. Usage: python tools/list_by_type.py <out.tsv> <type> [<type> ...]
Types: earrings necklaces rings belts heads production recipes supplies food potions magic-items
magic-stones ench-stones god-stones dyes titles skillbooks other (see the site's menu).
"""

import concurrent.futures as cf
import html
import re
import sys
import time
import urllib.request

SITE = "https://kb.aionempire.com"
HEADERS = {"User-Agent": "Mozilla/5.0", "Cookie": "PLAY_LANG=ru"}
ROW = re.compile(
    r'data-href="/items/(\d+)".*?class="li-i-n ([a-z]+)"[^>]*>([^<]*)</a>.*?item-quantity">[^<\d]*(\d+)',
    re.S,
)
BATCH = 8  # pages fetched in parallel; listing stops at the first empty page


def fetch(site_type: str, page: int) -> list[tuple[str, str, str, str]]:
    for attempt in range(4):
        try:
            url = f"{SITE}/items?type={site_type}&p={page}"
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
                text = r.read().decode("utf-8", "replace")
            return [(i, g, lvl, html.unescape(n).strip()) for i, g, n, lvl in ROW.findall(text)]
        except Exception as exc:  # retry transient errors
            error = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{site_type} page {page}: {error}")


def list_type(site_type: str) -> dict[str, tuple]:
    rows: dict[str, tuple] = {}
    page = 1
    with cf.ThreadPoolExecutor(BATCH) as pool:
        while True:
            pages = list(pool.map(lambda p: fetch(site_type, p), range(page, page + BATCH)))
            for result in pages:
                for row in result:
                    rows[row[0]] = (*row, site_type)
            if any(not result for result in pages):
                return rows
            page += BATCH


def main() -> int:
    out, types = sys.argv[1], sys.argv[2:]
    rows: dict[str, tuple] = {}
    for site_type in types:
        found = list_type(site_type)
        print(f"{site_type}: {len(found)}", flush=True)
        for item_id, row in found.items():
            rows.setdefault(item_id, row)  # first listed type wins
    with open(out, "w", encoding="utf-8") as f:
        for row in sorted(rows.values(), key=lambda r: int(r[0])):
            f.write("\t".join(row) + "\n")
    print(f"done: {len(rows)} items -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
