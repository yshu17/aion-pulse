"""Golden results of core/map/poi.py and the spawn circle for the TypeScript port (tests/golden/map_*.json).

The real data/maps/poi.json is checked by a digest in which every coordinate is round(v * 100), so Python's «1.0» and
JavaScript's «1» print the same; zone 600010000 (13 points) and 400010000 (layers) are kept in full.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POI = ROOT / "data" / "maps" / "poi.json"


def row(p):
    return [p.zone, p.type, p.x, p.y, p.gx, p.gy, p.name, p.note, p.side, p.layer]


def coded(p):
    return [p.zone, p.type, *(round(v * 100) for v in (p.x, p.y, p.gx, p.gy)), p.name, p.note, p.side, p.layer]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def poi_cases() -> dict:
    from core.map.poi import PoiStore

    store = PoiStore.load(POI)
    zones = sorted(store._zones)
    tmp = Path(tempfile.mkdtemp())
    broken = []
    for i, text in enumerate([None, "{bad", "[]", '{"zones": []}', '{"zones": {"1": 5}}', '{"zones": {"1": [[1]]}}',
                              '{"zones": {"1": [{"t": "a", "x": 1, "y": 2, "gx": 3}]}}', '{"types": [1]}',
                              '{"types": [["a", {"name": "A"}], "bc"], "zones": {"1": [{"t": "a", "x": 1, "y": 2, '
                              '"gx": 3, "gy": 4, "name": null, "layer": 2}]}}',
                              '{"types": [["a", 1, 2]]}', '{"types": {"a": {"group": "g"}}, "zones": {}}']):
        path = tmp / f"p{i}.json"
        if text is not None:
            path.write_text(text, encoding="utf-8")
        s = PoiStore.load(path)
        broken.append([text, s.types, {z: [row(p) for p in ps] for z, ps in s._zones.items()}])

    in_zone = []
    for zone in ("600010000", "210040000", "400010000", "999"):
        for types in (["quest_give", "portal", "dungeon"], ["merchant"], []):
            for side in ("", "dark", "light"):
                for layer in (None, 1, 3):
                    found = store.in_zone(zone, set(types), side, layer)
                    in_zone.append([zone, types, side, layer, digest([coded(p) for p in found]), len(found)])
    all_types = list(store.types)
    search = [[zone, q, side, [row(p) for p in store.search(zone, q, set(all_types), side)]]
              for zone, q, side in (("600010000", "портал", ""), ("210040000", "торговец", "light"),
                                    ("210040000", "  ", ""), ("220070000", "ЁЛКА", "dark"), ("220070000", "ст", ""),
                                    ("400010000", "крепость", "dark"), ("120010000", "склад хранилище", ""))]
    nearest = []
    for zone, gx, gy, t in (("210040000", 1000.0, 1000.0, "teleport"), ("210040000", 0, 0, "bindstone"),
                            ("400010000", 1500.5, 2200.25, "fortress"), ("110020000", 5, 5, "merchant"),
                            ("999", 0, 0, "teleport")):
        r = store.nearest(zone, gx, gy, t)
        nearest.append([zone, gx, gy, t, None if r is None else [row(r[0]), r[1]]])

    def f(gx, gy):
        return gx * 0.5 + 3.25, -gy * 0.25 + 100.0

    projected = store.projected({"600010000": f, "110020000": lambda gx, gy: (gy / 3, gx / 7)})
    return {
        "types": store.types, "groups": store.groups(),
        "type_names": [[t, store.type_name(t)] for t in all_types + ["nope"]],
        "zones": {z: [len(store._zones[z]), digest([coded(p) for p in store._zones[z]])] for z in zones},
        "full": {z: [row(p) for p in store._zones[z]] for z in ("600010000", "400010000")},
        "counts": {z: store.counts(z) for z in zones + ["999"]},
        "broken": broken, "in_zone": in_zone, "search": search, "nearest": nearest,
        "projected": {z: [row(p) for p in projected._zones[z]] for z in ("600010000", "110020000", "120020000")},
    }


def cluster_cases() -> dict:
    """Clusters of the projected points (x = gx * 0.5 + 3.25, y = -gy * 0.25 + 100) at several zooms and pans."""
    from core.map.poi import PoiStore, cluster
    from core.map.zones import enclosing_spawn_circle

    raw = PoiStore.load(POI)
    # most points of the file keep image x, y = 0 (the program projects game coordinates), so do the same here
    store = raw.projected({z: (lambda gx, gy: (gx * 0.5 + 3.25, -gy * 0.25 + 100.0)) for z in raw._zones})
    out = []
    for zone in ("210040000", "400010000", "600010000"):
        points = store.in_zone(zone, set(store.types))
        for scale, dx, dy in ((1.0, 0.0, 0.0), (0.37, -125.5, 48.25), (2.5, 333.3, -1000.1), (0.1, 7.7, 7.7)):
            for radius in (28.0, 9.5, 120.0):
                groups = cluster(points, lambda x, y: (x * scale + dx, y * scale + dy), radius)
                out.append([zone, scale, dx, dy, radius,
                            [[cx, cy, [points.index(m) for m in members]] for cx, cy, members in groups]])
    by_side = cluster(store.in_zone("220070000", set(store.types)), lambda x, y: (x * 0.5, y * 0.5), 40.0,
                      key=lambda p: p.side or "-")
    circles = [[polys, None if (c := enclosing_spawn_circle(polys)) is None else list(c)] for polys in
               ([], [[]], [[(0, 0), (100, 0)]], [[(1.5, 2.5)]], [[(10, 10), (20, 30)], [(-5.5, 7.25), (3, "4.5")]],
                [[(0.1, 0.2), (0.3, 0.7), (1e3, 3.3)]])]
    rnd = random.Random(7)  # Python's own math.hypot and sum() bits: the port must match them, not Math.hypot
    pairs = [[rnd.uniform(-3000, 3000), rnd.uniform(-3000, 3000)] for _ in range(2000)]
    pairs += [[rnd.uniform(-1, 1) * 10 ** rnd.randint(-8, 8), rnd.uniform(-1, 1) * 10 ** rnd.randint(-8, 8)] for _ in range(500)]
    sums = [[rnd.uniform(-1, 1) * 10 ** rnd.randint(-3, 6) for _ in range(rnd.randint(1, 40))] for _ in range(300)]
    numeric = {"hypot": [[x, y, math.hypot(x, y)] for x, y in pairs], "sum": [[v, sum(v)] for v in sums]}
    return {"numeric": numeric, "cluster": out, "by_side": [[cx, cy, [row(m) for m in members]] for cx, cy, members in by_side],
            "circles": circles}


def all_cases() -> dict[str, dict]:
    return {"map_poi": poi_cases(), "map_cluster": cluster_cases()}
