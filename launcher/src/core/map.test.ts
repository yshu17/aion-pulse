// Step 6 of the port: map points of interest and the spawn circle replay the Python golden results (tools/golden_map.py).
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { cluster, Poi, PoiStore } from "./map/poi";
import { enclosingSpawnCircle } from "./map/zones";
import { pyHypot, pyRound, pySum } from "./py";

const ROOT = join(__dirname, "..", "..", "..");
const golden = (name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "golden", `${name}.json`), "utf-8")).case;
const POI = readFileSync(join(ROOT, "data", "maps", "poi.json"), "utf-8");

/** json.dumps(value, ensure_ascii=False, sort_keys=True) of Python, for strings, integers, lists and objects. */
function pyDumps(value: unknown): string {
  if (Array.isArray(value)) return "[" + value.map(pyDumps).join(", ") + "]";
  if (value && typeof value === "object") {
    return "{" + Object.keys(value).sort().map((k) => `${JSON.stringify(k)}: ${pyDumps((value as any)[k])}`).join(", ") + "}";
  }
  return JSON.stringify(value);
}
const digest = (value: unknown) => createHash("sha256").update(pyDumps(value), "utf-8").digest("hex");

const row = (p: Poi) => [p.zone, p.type, p.x, p.y, p.gx, p.gy, p.name, p.note, p.side, p.layer];
const coded = (p: Poi) => [p.zone, p.type, ...[p.x, p.y, p.gx, p.gy].map((v) => pyRound(v * 100)), p.name, p.note, p.side, p.layer];
const shift = (gx: number, gy: number): [number, number] => [gx * 0.5 + 3.25, -gy * 0.25 + 100.0];

describe("map points of interest", () => {
  const g = golden("map_poi");
  const store = PoiStore.load(POI);
  it("load, filter, count, search and find the nearest point as in Python", () => {
    expect(store.types).toEqual(g.types);
    expect(store.groups()).toEqual(g.groups);
    for (const [t, want] of g.type_names) expect(store.typeName(t)).toBe(want);
    const zones = Object.fromEntries(store.zoneIds().sort().map((z) => [z, [store.zone(z).length, digest(store.zone(z).map(coded))]]));
    expect(zones).toEqual(g.zones);
    for (const z of Object.keys(g.full)) expect(store.zone(z).map(row), z).toEqual(g.full[z]);
    for (const z of Object.keys(g.counts)) expect(store.counts(z), z).toEqual(g.counts[z]);
    for (const [text, types, zonesWant] of g.broken) {
      const s = PoiStore.load(text);
      expect([s.types, Object.fromEntries(s.zoneIds().map((z) => [z, s.zone(z).map(row)]))], String(text)).toEqual([types, zonesWant]);
    }
    for (const [zone, types, side, layer, want, count] of g.in_zone) {
      const found = store.inZone(zone, new Set(types), side, layer);
      expect([digest(found.map(coded)), found.length], JSON.stringify([zone, types, side, layer])).toEqual([want, count]);
    }
    const all = new Set(Object.keys(store.types));
    for (const [zone, q, side, want] of g.search) expect(store.search(zone, q, all, side).map(row), q).toEqual(want);
    for (const [zone, gx, gy, t, want] of g.nearest) {
      const r = store.nearest(zone, gx, gy, t);
      expect(r === null ? null : [row(r[0]), r[1]], `${zone} ${t}`).toEqual(want);
    }
    const projected = store.projected({ "600010000": shift, "110020000": (gx, gy) => [gy / 3, gx / 7] });
    for (const z of Object.keys(g.projected)) expect(projected.zone(z).map(row), z).toEqual(g.projected[z]);
  });
});

describe("map clusters and spawn circle", () => {
  const g = golden("map_cluster");
  const raw = PoiStore.load(POI);
  const store = raw.projected(Object.fromEntries(raw.zoneIds().map((z) => [z, shift])));
  const all = new Set(Object.keys(store.types));
  it("hypot and sum give Python's last bit", () => {
    let hypotDiffers = 0;
    for (const [x, y, want] of g.numeric.hypot) {
      expect(pyHypot(x, y), `${x} ${y}`).toBe(want);
      if (Math.hypot(x, y) !== want) hypotDiffers += 1;
    }
    expect(hypotDiffers).toBeGreaterThan(0); // the reason pyHypot exists
    for (const [values, want] of g.numeric.sum) expect(pySum(values)).toBe(want);
  });
  it("group close points and cover spawn areas as in Python", () => {
    for (const [zone, scale, dx, dy, radius, want] of g.cluster) {
      const points = store.inZone(zone, all);
      const got = cluster(points, (x, y) => [x * scale + dx, y * scale + dy], radius)
        .map(([cx, cy, members]) => [cx, cy, members.map((m) => points.indexOf(m))]);
      expect(got, JSON.stringify([zone, scale, dx, dy, radius])).toEqual(want);
    }
    const bySide = cluster(store.inZone("220070000", all), (x, y) => [x * 0.5, y * 0.5], 40.0, (p) => p.side || "-");
    expect(bySide.map(([cx, cy, members]) => [cx, cy, members.map(row)])).toEqual(g.by_side);
    for (const [polys, want] of g.circles) expect(enclosingSpawnCircle(polys), JSON.stringify(polys)).toEqual(want);
  });
});
