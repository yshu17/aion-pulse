import { describe, expect, it } from "vitest";

import { toGame } from "./view";
import { toImage, Zone } from "./zones";

const turned: Zone = {
  map_id: "120020000", name: "Храм Маркутана", file: "client/dc2.jpg", size: 1024,
  kx: [3.2, -4131.2], ky: [3.2, -4547.2], labels: [], layers: [], label_layers: [], side: "dark", kind: "zone", turn: -31,
};

describe("a picture turned about its centre (the temples' new maps)", () => {
  it("turns a point as PIL rotate(-31) turns the picture on the same 1024 canvas", () => {
    const [ix, iy] = toImage({ ...turned, turn: 0 }, 1500, 2100);
    const [tx, ty] = toImage(turned, 1500, 2100);
    const c = 512, t = (-31 * Math.PI) / 180;
    expect(tx).toBeCloseTo(c + (ix - c) * Math.cos(t) - (iy - c) * Math.sin(t), 6);
    expect(ty).toBeCloseTo(c + (ix - c) * Math.sin(t) + (iy - c) * Math.cos(t), 6);
  });

  it("gives back the game coordinates under a turned picture point", () => {
    const [px, py] = toImage(turned, 1500, 2100);
    const [gx, gy] = toGame(turned, px, py)!;
    expect(gx).toBeCloseTo(1500, 4);
    expect(gy).toBeCloseTo(2100, 4);
  });

  it("leaves a picture without a turn as it was", () => {
    const plain = { ...turned, turn: 0 };
    expect(toImage(plain, 1500, 2100)).toEqual([plain.kx[0] * 2100 + plain.kx[1], plain.ky[0] * 1500 + plain.ky[1]]);
  });
});
