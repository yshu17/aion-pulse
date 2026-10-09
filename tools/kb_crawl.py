"""Crawl kb.aionempire.com item list (RU names) into a TSV: id, grade, level, name."""
import concurrent.futures as cf
import html
import re
import sys
import time
import urllib.request

BASE = "https://kb.aionempire.com/items?p={}"
LANG = sys.argv[2] if len(sys.argv) > 2 else "ru"
HEADERS = {"User-Agent": "Mozilla/5.0", "Cookie": f"PLAY_LANG={LANG}"}
ROW = re.compile(
    r'data-href="/items/(\d+)".*?class="li-i-n ([a-z]+)"[^>]*>([^<]*)</a>.*?item-quantity">[^<\d]*(\d+)',
    re.S,
)


def fetch(page: int) -> list[tuple[str, str, str, str]]:
    for attempt in range(4):
        try:
            req = urllib.request.Request(BASE.format(page), headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                text = r.read().decode("utf-8", "replace")
            return [(i, g, lvl, html.unescape(n).strip()) for i, g, n, lvl in ROW.findall(text)]
        except Exception as e:  # retry transient errors
            time.sleep(2 * (attempt + 1))
            err = e
    print(f"page {page} failed: {err}", file=sys.stderr)
    return []


def main() -> None:
    out, last = sys.argv[1], 3095
    rows: dict[str, tuple] = {}
    with cf.ThreadPoolExecutor(4) as ex:
        for n, result in enumerate(ex.map(fetch, range(1, last + 1)), 1):
            for row in result:
                rows[row[0]] = row
            if n % 200 == 0:
                print(f"{n}/{last} pages, {len(rows)} items", flush=True)
    with open(out, "w", encoding="utf-8") as f:
        for row in sorted(rows.values(), key=lambda r: int(r[0])):
            f.write("\t".join(row) + "\n")
    print(f"done: {len(rows)} items -> {out}")


if __name__ == "__main__":
    main()
