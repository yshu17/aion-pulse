"""Golden results of the Python core, the reference for the TypeScript port (launcher/, branch pulse+).

    python tools/golden_gen.py            # rewrite tests/golden/*.json from the current core
    python -m pytest tests/test_golden.py # check the files still match the core

Each file is {"case": {...}} with inputs and the expected output. Real bundled data is summarised by counts and a hash,
so the files stay small and the port is still checked against the real data.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
GOLDEN = ROOT / "tests" / "golden"


def _digest(value) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def settings_cases() -> dict:
    from core.settings.config import Config, read_config, save_config

    defaults = asdict(Config())
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "config.json"
        path.write_text(json.dumps({
            "keywords": ["wts", 5], "cooldown_sec": 30, "alert_mode": "nag", "react_sec": "30",
            "notify_corner": "top", "unknown_key": 1,
        }, ensure_ascii=False), encoding="utf-8")
        cfg, notice = read_config(path)
        mixed = asdict(cfg)
        path.write_text("не json", encoding="utf-8")
        broken_cfg, broken_notice = read_config(path)
        save_config(path, Config(keywords=["хил"], watch_items=["1"]))
        saved = json.loads(path.read_text(encoding="utf-8"))
    return {
        "defaults": defaults,
        "mixed_types": {"config": mixed, "notice": notice},
        "broken_file": {"config": asdict(broken_cfg), "notice_starts": broken_notice[:20]},
        "saved_keys": {"keywords": saved["keywords"], "watch_items": saved["watch_items"]},
    }


def loader_cases() -> dict:
    from core.items.catalog import load_item_names, load_link_names, load_watch_items
    from core.map.zones import load_zones

    data = ROOT / "data"
    names = load_item_names(data / "item_names.tsv")
    maps, quests = load_link_names(data)
    watch = load_watch_items(data / "watch_items.csv")
    zones = load_zones(data / "maps", maps)
    sample_id = sorted(names)[0]
    return {
        "item_names": {"count": len(names), "digest": _digest(sorted(names.items())), "sample": [sample_id, names[sample_id]]},
        "link_names": {"maps": len(maps), "quests": len(quests), "digest": _digest([sorted(maps.items()), sorted(quests.items())])},
        "watch_items": {"count": len(watch), "digest": _digest([[w.id, w.name, w.level, w.category, w.grade, w.kind] for w in watch])},
        # zones in full: their coefficients are floats such as 1.0 and -0.0, which Python and JavaScript print
        # differently, so a hash of the text would not match; the values themselves do
        "zones": {"count": len(zones), "list": [
            {"map_id": z.map_id, "name": z.name, "file": z.path.name, "size": z.size, "kx": list(z.kx),
             "ky": list(z.ky), "side": z.side, "labels": len(z.labels), "layers": [layer[0] for layer in z.layers]}
            for z in sorted(zones.values(), key=lambda zone: zone.map_id)]},
    }


def write_all() -> list[Path]:
    GOLDEN.mkdir(parents=True, exist_ok=True)
    written = []
    for name, build in (("settings", settings_cases), ("loaders", loader_cases)):
        path = GOLDEN / f"{name}.json"
        path.write_text(json.dumps({"case": build()}, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for path in write_all():
        print("written", path.relative_to(ROOT))
