"""Build the bundled item data from the crawl cache (see tools/crawl_items.py).

Writes:
  data/watch_items.csv     id,name,level,category,grade,icon,kind — catalog; the «Что искать» list
                           shows its listed part (see core.items.catalog.is_listed)
  data/item_specs.json.gz  item id -> tooltip spec (compact JSON text, parsed on demand)
  data/icons/<icon>.png    one picture per distinct site icon, 56 px
Dev tool (needs Pillow). Usage: python tools/build_catalog.py <cache.jsonl> [<cache.jsonl> ...]
"""

import concurrent.futures as cf
import csv
import gzip
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.items.catalog import CATEGORY_ORDER, category_for  # noqa: E402

SITE = "https://kb.aionempire.com"
HEADERS = {"User-Agent": "Mozilla/5.0", "Cookie": "PLAY_LANG=ru"}
ICON_SIZE = 56
ICON_CONTENT = 40  # site icons are 64x64 sprites with the picture in the top-left 40x40
GRADE_RANK = {"finality": 0, "mythic": 1, "epic": 2, "unique": 3, "legend": 4, "rare": 5, "common": 6}
PREFIX_CATEGORY = {"115": "Щиты", "187": "Крылья"}  # these pages have no «Тип»
# site list type (tools/list_by_type.py) -> (category, kind)
SITE_TYPES = {
    "earrings": ("Украшения", "Серьги"),
    "necklaces": ("Украшения", "Ожерелья"),
    "rings": ("Украшения", "Кольца"),
    "belts": ("Украшения", "Пояса"),
    "heads": ("Головные уборы", ""),
    "production": ("Изготовление", "Материалы"),
    "recipes": ("Изготовление", "Рецепты"),
    "supplies": ("Припасы", "Еда"),  # the site's «Припасы» list holds only food
    "food": ("Припасы", "Еда"),
    "potions": ("Припасы", "Зелья"),
    "magic-items": ("Припасы", "Магич. предметы"),
    "magic-stones": ("Припасы", "Магич. камни"),
    "ench-stones": ("Припасы", "Волшебные камни"),
    "god-stones": ("Припасы", "Божеств. камни"),
    "dyes": ("Припасы", "Краски"),
    "titles": ("Прочее", "Титулы"),
    "skillbooks": ("Прочее", "Умения"),
    "other": ("Прочее", ""),
}


def item_type(spec: dict) -> str:
    for block in spec["blocks"]:
        if block["kind"] == "pairs":
            for name, value in block["rows"]:
                if name == "Тип":
                    return value
    return ""


def category(item: dict) -> tuple[str, str]:
    """(category, kind) — kind is the weapon type or accessory type, used by the list filter."""
    if item.get("type") in SITE_TYPES:
        return SITE_TYPES[item["type"]]
    spec_type = item_type(item["spec"])
    found = category_for(spec_type, item["name"])
    if found == "Прочее":
        found = PREFIX_CATEGORY.get(item["id"][:3], found)
    return found, spec_type if found == "Оружие" else ""


def save_icon(name: str, path: Path) -> str:
    from PIL import Image

    request = urllib.request.Request(f"{SITE}/assets/images/icons/{name}", headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        return f"{name}: {exc.code}"
    except OSError as exc:
        return f"{name}: {exc}"
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    image = image.crop((0, 0, ICON_CONTENT, ICON_CONTENT)).resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
    save_small(image, path)
    return ""


def save_small(image, path: Path) -> None:
    """256-colour PNG: about half the size of full colour, no visible difference at 56 px."""
    from PIL import Image

    image.convert("RGB").quantize(256, method=Image.Quantize.MEDIANCUT).save(path, optimize=True)


def shrink_old_icons(icons_dir: Path) -> int:
    """Convert full-colour icons left from older builds to 256 colours."""
    from PIL import Image

    count = 0
    for path in icons_dir.glob("*.png"):
        with Image.open(path) as image:
            if image.mode == "P":
                continue
            image.load()
        save_small(image, path)
        count += 1
    return count


def main() -> int:
    data = ROOT / "data"
    icons_dir = data / "icons"
    icons_dir.mkdir(exist_ok=True)
    items = {}
    for cache in sys.argv[1:]:
        with open(cache, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    items.setdefault(item["id"], item)
    for item in items.values():
        item["category"], item["kind"] = category(item)
    order = {name: i for i, name in enumerate(CATEGORY_ORDER)}
    rows = sorted(
        items.values(),
        key=lambda i: (order[i["category"]], -i["level"], GRADE_RANK.get(i["grade"], 9), i["name"], i["id"]),
    )
    with open(data / "watch_items.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["id", "name", "level", "category", "grade", "icon", "kind"])
        for i in rows:
            writer.writerow(
                [i["id"], i["name"], i["level"], i["category"], i["grade"], Path(i["icon"]).stem, i["kind"]]
            )
    specs = {i["id"]: json.dumps(i["spec"], ensure_ascii=False, separators=(",", ":")) for i in rows}
    blob = json.dumps(specs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    (data / "item_specs.json.gz").write_bytes(gzip.compress(blob, 9))

    wanted = {i["icon"] for i in rows if i["icon"]}
    missing = [name for name in sorted(wanted) if not (icons_dir / f"{Path(name).stem}.png").exists()]
    with cf.ThreadPoolExecutor(6) as pool:
        errors = [e for e in pool.map(lambda n: save_icon(n, icons_dir / f"{Path(n).stem}.png"), missing) if e]
    shrunk = shrink_old_icons(icons_dir)
    keep = {f"{Path(name).stem}.png" for name in wanted}
    stale = [p for p in icons_dir.glob("*.png") if p.name not in keep]
    for path in stale:
        path.unlink()
    counts = {c: sum(1 for i in rows if i["category"] == c) for c in CATEGORY_ORDER}
    print(f"{len(rows)} items {counts}")
    print(
        f"{len(wanted)} icons ({len(missing)} downloaded, {len(errors)} unavailable, "
        f"{len(stale)} old removed, {shrunk} shrunk to 256 colours)"
    )
    for error in errors:
        print("  no icon:", error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
