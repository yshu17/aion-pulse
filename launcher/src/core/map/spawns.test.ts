import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { nearestPoint, spawnAreas, Spawns } from "./spawns";
import { parseZones } from "./zones";

const ROOT = join(__dirname, "..", "..", "..", "..");
const read = (path: string) => readFileSync(join(ROOT, "data", path), "utf-8");

describe("NPC and monster points (spawns.json)", () => {
  const spawns = Spawns.parse(read("maps/spawns.json"));
  const zones = parseZones(read("maps/maps.json"), read("maps/labels.tsv"), {}, () => true);

  it("covers zones that have a map, with names for every NPC", () => {
    expect(spawns.size).toBeGreaterThan(5000);
    const found = spawns.find("статуя телепорта");
    expect(found.length).toBeGreaterThan(0);
    for (const f of found) {
      expect(f.name.toLowerCase()).toContain("статуя телепорта");
      for (const z of f.zones) expect(zones[z.map_id], z.map_id).toBeDefined();
    }
  });

  it("ranks the exact name first, keeps NPCs of one name apart and ignores short queries", () => {
    const [first] = spawns.find("Кибелиск");
    expect(first.name).toBe("Кибелиск");
    expect(spawns.find("к")).toEqual([]);
    const total = spawns.find("кибелиск", 200).reduce((n, f) => n + f.total, 0);
    expect(total).toBeGreaterThan(first.total);
  });

  it("gives an NPC's points in a zone and the nearest of them", () => {
    const [f] = spawns.find("Кибелиск");
    const zone = f.zones[0].map_id;
    const points = spawns.points(f.npc, zone);
    expect(points.length).toBe(f.zones[0].count);
    expect(nearestPoint(points, points[0][0], points[0][1])).toEqual(points[0]);
    expect(spawns.points(f.npc, "no-such-zone")).toEqual([]);
  });

  it("puts the dungeons of the client into the map, inside their pictures", () => {
    const tamares = zones["300310000"];
    expect(tamares.layers.length).toBe(3);
    const [f] = spawns.find("Тамарэс").filter((s) => s.zones.some((z) => z.map_id === "300310000"));
    if (f) {
      for (const [x, y] of spawns.points(f.npc, "300310000")) {
        const ix = tamares.kx[0] * y + tamares.kx[1], iy = tamares.ky[0] * x + tamares.ky[1];
        expect(ix).toBeGreaterThanOrEqual(0);
        expect(iy).toBeLessThanOrEqual(tamares.size);
      }
    }
  });

  it("gives an empty index for a missing or broken file", () => {
    expect(Spawns.parse(null).size).toBe(0);
    expect(Spawns.parse("{").size).toBe(0);
  });

  it("knows the NPCs the client names only by spawn points (SP): they may appear on a condition", () => {
    const small = Spawns.parse(JSON.stringify({ names: { "1": "Обычный", "2": "Только SP" }, sp_only: ["2"],
      zones: { "220070000": [["1", 1, 1, 0], ["2", 5, 5, 0]] } }));
    expect(small.spOnly("2")).toBe(true);
    expect(small.spOnly("1")).toBe(false);
    expect(Spawns.parse(null).spOnly("2")).toBe(false); // an older file without the list
    expect(spawns.spOnly("nobody")).toBe(false);
    const found = spawns.find("королева ньютиона", 3);
    expect(found.length).toBeGreaterThan(0);
  });

  it("lists the decorative NPCs of a zone (the small blue dots), each point with its NPC", () => {
    const small = Spawns.parse(JSON.stringify({ names: { "1": "Житель", "2": "Страж" }, deco: ["1"],
      zones: { "220070000": [["1", 10, 20, 0], ["2", 30, 40, 0], ["1", 50, 60, 0]], "220040000": [["1", 1, 1, 0]] } }));
    expect(small.isDeco("1")).toBe(true);
    expect(small.isDeco("2")).toBe(false);
    expect(small.decoPoints("220070000")).toEqual([{ npc: "1", x: 10, y: 20 }, { npc: "1", x: 50, y: 60 }]);
    expect(small.decoPoints("999")).toEqual([]);
    expect(Spawns.parse(null).decoPoints("220070000")).toEqual([]); // an older file without the list
  });

  it("joins spawn points that are close into one area, far ones get their own", () => {
    const areas = spawnAreas([[0, 0, 0], [100, 0, 0], [50, 80, 0], [2000, 2000, 0]], 110);
    expect(areas).toHaveLength(2);
    const [near, far] = areas;
    expect(near.x).toBeCloseTo(50);
    expect(near.y).toBeCloseTo(80 / 3);
    for (const [x, y] of [[0, 0], [100, 0], [50, 80]]) expect(Math.hypot(x - near.x, y - near.y) + 110).toBeLessThanOrEqual(near.r + 1e-9);
    expect(far).toEqual({ x: 2000, y: 2000, r: 110 });
    expect(spawnAreas([], 110)).toEqual([]);
  });
});
