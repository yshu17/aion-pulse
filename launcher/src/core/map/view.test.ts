import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { PoiStore } from "./poi";
import { centreOn, clampView, fitView, gameAt, iconSize, labelLevels, MAX_ZOOM, nearby, shownTypes, toScreen, zoomAt,
  zonesOfSide } from "./view";
import { parseZones, toImage } from "./zones";

const ROOT = join(__dirname, "..", "..", "..", "..");
const read = (path: string) => readFileSync(join(ROOT, "data", path), "utf-8");
const zones = parseZones(read("maps/maps.json"), read("maps/labels.tsv"), { "220070000": "Келькмарос" }, () => true);
const zone = zones["220070000"];
const store = PoiStore.load(read("maps/poi.json")).projected(
  Object.fromEntries(Object.entries(zones).map(([id, z]) => [id, (gx: number, gy: number) => toImage(z, gx, gy)])));
const W = 1000, H = 800;

describe("map view", () => {
  it("fits the zone in the smaller side, centred", () => {
    const v = fitView(zone, W, H);
    expect(v.zoom).toBeCloseTo(H / zone.size);
    const [x0, y0] = toScreen(v, 0, 0);
    const [x1, y1] = toScreen(v, zone.size, zone.size);
    expect((x0 + x1) / 2).toBeCloseTo(W / 2);
    expect(y0).toBeCloseTo(0);
    expect(y1).toBeCloseTo(H);
  });

  it("zooms around the mouse: the point under it stays, the zoom stays between the fit and the maximum", () => {
    const v = fitView(zone, W, H);
    const z = zoomAt(v, v.zoom * 2, 400, 300, zone, W, H);
    const before = [v.left + 400 / v.zoom, v.top + 300 / v.zoom];
    const after = [z.left + 400 / z.zoom, z.top + 300 / z.zoom];
    expect(after[0]).toBeCloseTo(before[0]);
    expect(after[1]).toBeCloseTo(before[1]);
    expect(zoomAt(v, 99, 0, 0, zone, W, H).zoom).toBe(MAX_ZOOM);
    expect(zoomAt(v, 0.0001, 0, 0, zone, W, H).zoom).toBeCloseTo(v.zoom);
  });

  it("lets a point at the edge come to the centre, but not further", () => {
    const close = { zoom: 2, left: 0, top: 0 };
    const centred = centreOn(close, 0, 0, zone, W, H);
    expect(toScreen(centred, 0, 0)).toEqual([W / 2, H / 2]);
    const far = clampView({ zoom: 2, left: -5000, top: -5000 }, zone, W, H);
    expect(far.left).toBeCloseTo(-W / 2 / 2);
  });

  it("lets a picture smaller than the view move, but only while it stays whole inside", () => {
    const v = fitView(zone, W, H); // wider than tall: the picture is narrower than the view
    const moved = clampView({ ...v, left: v.left - 50 }, zone, W, H);
    expect(moved.left).toBeCloseTo(v.left - 50);
    const far = clampView({ ...v, left: -1e6 }, zone, W, H);
    expect(toScreen(far, zone.size, 0)[0]).toBeCloseTo(W); // its right edge at the view's right edge
  });

  it("gives the game coordinates under the mouse back (the inverse of toImage)", () => {
    const v = { zoom: 1.5, left: 100, top: 200 };
    const [ix, iy] = toImage(zone, 1500, 2100);
    const [sx, sy] = toScreen(v, ix, iy);
    const [gx, gy] = gameAt(v, zone, sx, sy)!;
    expect(gx).toBeCloseTo(1500);
    expect(gy).toBeCloseTo(2100);
  });

  it("sizes icons as Pulse: teleporters bigger, fortresses much bigger", () => {
    expect(iconSize("merchant", 0.3)).toBe(28);
    expect(iconSize("teleport", 0.3)).toBe(36);
    expect(iconSize("fortress", 4)).toBe(Math.round(40 * 1.85));
  });

  it("draws area names only when the zone is big enough on screen", () => {
    expect(labelLevels(zone, 1000 / zone.size).size).toBe(0);
    expect([...labelLevels(zone, 2000 / zone.size)]).toEqual(["main"]);
    expect([...labelLevels(zone, 5000 / zone.size)]).toEqual(["main", "zoom"]);
  });

  it("leaves out the types of switched-off filter groups", () => {
    expect(shownTypes(store, []).has("teleport")).toBe(true);
    expect(shownTypes(store, ["teleports"]).has("teleport")).toBe(false);
  });

  it("finds the nearest useful points of the zone, closest first per type", () => {
    const point = store.zone("220070000").find((p) => p.type === "teleport")!;
    const near = nearby(store, "220070000", point.gx, point.gy, "dark", null);
    const teleport = near.find((n) => n.type === "teleport")!;
    expect(teleport.metres).toBe(0);
    const other = nearby(store, "220070000", point.gx, point.gy, "dark", null, point).find((n) => n.type === "teleport");
    expect(other === undefined || other.metres > 0).toBe(true);
  });

  it("lists a side's zones: shared and its own, by name", () => {
    const dark = zonesOfSide(zones, "dark");
    expect(dark.every((z) => z.side !== "light")).toBe(true);
    expect(dark.length).toBeGreaterThan(0);
  });
});
