import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { nearestPoint, Spawns } from "./spawns";
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
});
