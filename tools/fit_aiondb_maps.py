"""Fit game -> aiondb image transform per zone from NPCs found both on aiondb and in the client.

Input: downloads/aiondb_maps/aiondb_npcs.csv (zone, type, npc_id, svg cx, cy from the aiondb zone pages),
client_extract/client_npcs.tsv and client_level_objects.tsv. Output: downloads/aiondb_maps/fit.json.
The result went into data/maps/maps.json (map plan v3). Dev tool. Usage: python tools/fit_aiondb_maps.py
"""
import csv
import json
from collections import defaultdict

VIEW = {"dc1": 705, "df1": 2300, "df1a": 2790, "underpass": 1536}
ZONE_ID = {"dc1": "120010000", "df1": "220010000", "df1a": "220030000", "df2": "220020000", "df2a": "220050000",
           "df3": "220040000", "df4": "220070000", "lf4": "210050000", "underpass": "600010000"}
ex = "client_extract/"
dl = "downloads/"
names = {r["npc_id"]: r["internal_name"].lower() for r in csv.DictReader(open(ex + "client_npcs.tsv", encoding="utf-8"), delimiter="\t")}
spawns = defaultdict(list)  # (zone code, internal name) -> [(gx, gy)]
for r in csv.DictReader(open(ex + "client_level_objects.tsv", encoding="utf-8"), delimiter="\t"):
    if r["npc_internal_name"]:
        spawns[(r["zone"], r["npc_internal_name"].lower())].append((float(r["game_x"]), float(r["game_y"])))


def lsq(pairs):
    n = len(pairs)
    mx = sum(p for p, _ in pairs) / n
    my = sum(q for _, q in pairs) / n
    sxx = sum((p - mx) ** 2 for p, _ in pairs)
    a = sum((p - mx) * (q - my) for p, q in pairs) / sxx
    return a, my - a * mx


out = {}
for zone in ZONE_ID:
    rows = [r for r in csv.DictReader(open(dl + "aiondb_maps/aiondb_npcs.csv")) if r["zone"] == zone]
    k = 3072 / VIEW.get(zone, 3072)
    pts = []
    for r in rows:
        cands = spawns.get((zone, names.get(r["npc_id"], "?")), [])
        if len(cands) == 1:  # unique spawn only
            gx, gy = cands[0]
            pts.append((gx, gy, float(r["cx"]) * k, float(r["cy"]) * k, r["npc_id"]))
    if len(pts) < 3:
        print(zone, "too few", len(pts))
        continue
    for _ in range(3):  # drop outliers (server moved NPC)
        ax = lsq([(gy, ix) for gx, gy, ix, iy, _ in pts])
        ay = lsq([(gx, iy) for gx, gy, ix, iy, _ in pts])
        err = [abs(ax[0] * gy + ax[1] - ix) + abs(ay[0] * gx + ay[1] - iy) for gx, gy, ix, iy, _ in pts]
        med = sorted(err)[len(err) // 2]
        keep = [p for p, e in zip(pts, err) if e <= max(3 * med, 15)]
        if len(keep) == len(pts) or len(keep) < 3:
            break
        pts = keep
    err = [abs(ax[0] * gy + ax[1] - ix) + abs(ay[0] * gx + ay[1] - iy) for gx, gy, ix, iy, _ in pts]
    print(f"{zone}: n={len(pts)} x={ax[0]:.4f},{ax[1]:.1f} y={ay[0]:.4f},{ay[1]:.1f} err max {max(err):.1f} px")
    out[ZONE_ID[zone]] = {"file": f"aiondb/{zone}.jpg", "size": 3072, "x": [round(ax[0], 6), round(ax[1], 2)],
                          "y": [round(ay[0], 6), round(ay[1], 2)], "n": len(pts), "err_px": round(max(err), 1)}
json.dump(out, open(dl + "aiondb_maps/fit.json", "w"), indent=1)
