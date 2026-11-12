"""Copy the game pictures pulse.db needs from the fresh client export into data/icons (map:45, step 4).

    python tools/sync_catalog_icons.py            # copies, writes data/icons/fresh_catalog_icons.json

- items: a picture of client_extract/fresh_catalog/icons/items whose name data/icons lacks goes to data/icons/<name>.png.
  A name data/icons already has is kept: those are the older 56×56 copies the tabs use today (the export's are 64×64 of the
  same art, measured below); they are listed, not replaced.
- skills: only the skills the skill books and the stigmas point to (and the stigmas' own skills) → data/icons/skills/.
- pets: every pet picture → data/icons/pets/.
The names the export could not find in the client's PAKs (manifest.json «icons_unresolved») are looked up in the pictures the
project already has (data/icons, data/bestiary/icons); what is still missing is listed with its ids. Nothing is invented.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from crop_icons import crop_padded  # noqa: E402 - the 64×64 textures hold a 40×40 picture

FRESH = ROOT / "client_extract" / "fresh_catalog"
ICONS = ROOT / "data" / "icons"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def needed_skills(db: sqlite3.Connection) -> set[str]:
    """The lower-case internal names of the skills books and stigmas point to, and the stigmas' own skills."""
    names: set[str] = set()
    for (fields,) in db.execute("SELECT e.fields_json FROM entries e JOIN categories c ON c.section = e.section AND c.id = e.id "
                                "WHERE c.category IN ('skill_books', 'stigmas')"):
        f = json.loads(fields)
        for key in ("skill_to_learn", "gain_skill1", "require_skill1", "require_skill2"):
            if f.get(key):
                names.add(str(f[key]).lower())
    names.update((n or "").lower() for (n,) in db.execute(
        "SELECT e.internal_name FROM entries e JOIN categories c ON c.section = e.section AND c.id = e.id WHERE c.category = 'stigma_skills'"))
    return names


def same_art(old: Path, new: Path) -> float | None:
    """Mean difference 0…255 of the export's picture scaled to the old one's size (None without Pillow)."""
    try:
        from PIL import Image, ImageChops, ImageStat
    except ImportError:
        return None
    a = Image.open(old).convert("RGB")
    b = Image.open(new).convert("RGB").resize(a.size, Image.LANCZOS)
    return round(sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3, 1)


def main() -> int:
    db = sqlite3.connect(f"file:{(FRESH / 'catalog.sqlite').as_posix()}?mode=ro", uri=True)
    have = {p.name.lower() for p in ICONS.glob("*.png")}
    report: dict = {"source": "client_extract/fresh_catalog/icons (tools/export_fresh_catalog.py, client PAK 03.11.2026)",
                    "copied": {"items": [], "skills": [], "pets": []}, "kept_existing_items": 0, "kept_art_difference": None,
                    "unresolved": {}}

    diffs = []
    for src in sorted((FRESH / "icons" / "items").glob("*.png")):
        name = src.name.lower()
        if name in have:
            report["kept_existing_items"] += 1
            if len(diffs) < 200:  # a sample is enough to show the art is the same
                d = same_art(ICONS / name, src)
                if d is not None:
                    diffs.append(d)
            continue
        shutil.copyfile(src, ICONS / name)
        crop_padded(ICONS / name)
        report["copied"]["items"].append([name, sha(src)])
    if diffs:
        report["kept_art_difference"] = {"sample": len(diffs), "mean": round(sum(diffs) / len(diffs), 1), "max": max(diffs),
                                         "note": "mean channel difference 0…255 after scaling 64→56; small = the same picture"}

    wanted = needed_skills(db)
    skill_files = {(n or "").lower(): Path(p).name for n, p in db.execute(
        "SELECT internal_name, icon_path FROM entries WHERE section = 'skills' AND icon_path IS NOT NULL")}
    (ICONS / "skills").mkdir(exist_ok=True)
    for name in sorted({skill_files[n] for n in wanted if n in skill_files}):
        src = FRESH / "icons" / "skills" / name
        if src.is_file():
            shutil.copyfile(src, ICONS / "skills" / name.lower())
            crop_padded(ICONS / "skills" / name.lower())
            report["copied"]["skills"].append([name.lower(), sha(src)])

    (ICONS / "pets").mkdir(exist_ok=True)
    for src in sorted((FRESH / "icons" / "pets").glob("*.png")):
        shutil.copyfile(src, ICONS / "pets" / src.name.lower())
        crop_padded(ICONS / "pets" / src.name.lower())
        report["copied"]["pets"].append([src.name.lower(), sha(src)])

    manifest = json.loads((FRESH / "manifest.json").read_text(encoding="utf-8"))
    others = {p.name.lower(): p for folder in (ICONS, ROOT / "data" / "bestiary" / "icons") if folder.is_dir()
              for p in folder.rglob("*.png")}
    for section, names in (manifest.get("icons_unresolved") or {}).items():
        names = names if isinstance(names, list) else list(names)
        rows = []
        for entry in names:
            key = entry if isinstance(entry, str) else entry.get("icon") or entry.get("name") or json.dumps(entry)
            stem = Path(str(key)).stem.lower()
            ids = [i for (i,) in db.execute(f"SELECT id FROM entries WHERE section = ? AND lower(icon_key) LIKE ?", (section, f"{stem}%"))]
            found = others.get(f"{stem}.png")
            rows.append({"icon": stem, "ids": ids, "found": str(found.relative_to(ROOT)).replace("\\", "/") if found else None})
        report["unresolved"][section] = rows

    out = ICONS / "fresh_catalog_icons.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"items copied {len(report['copied']['items'])}, kept {report['kept_existing_items']} ({report['kept_art_difference']}); "
          f"skills {len(report['copied']['skills'])}; pets {len(report['copied']['pets'])}")
    for section, rows in report["unresolved"].items():
        print(f"unresolved {section}: {len(rows)} names, found elsewhere {sum(1 for r in rows if r['found'])}, "
              f"ids without a picture {sum(len(r['ids']) for r in rows if not r['found'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
