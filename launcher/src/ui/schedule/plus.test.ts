import { describe, expect, it } from "vitest";

import { busyBlocks, plusAt } from "./plus";

// a day of 0–1440 minutes drawn 1 px per minute: y = minute
const px = (m: number) => m;
const day = busyBlocks([[960, 1080], [1200, 1260], [1260, 1440]], px); // 16–18, 20–21, 21–24

describe("the busy blocks of a day", () => {
  it("merge overlapping and touching events and keep their pixels", () => {
    expect(busyBlocks([[600, 720], [660, 780], [900, 960]], px)).toEqual([
      { s: 600, e: 780, top: 600, bottom: 780 }, { s: 900, e: 960, top: 900, bottom: 960 }]);
    expect(day).toEqual([{ s: 960, e: 1080, top: 960, bottom: 1080 }, { s: 1200, e: 1440, top: 1200, bottom: 1440 }]);
  });
});

describe("where the plus stands", () => {
  it("in a free gap: on its middle, from the gap's start, two hours at most", () => {
    expect(plusAt(day, 1130, 1440)).toEqual({ y: 1140, from: 1080, to: 1200, edge: "gap" });
    expect(plusAt(day, 300, 1440)).toEqual({ y: 480, from: 0, to: 120, edge: "gap" });
  });

  it("on the nearest edge when the gap is too small for a plus of its own: an hour after or before the block", () => {
    const close = busyBlocks([[600, 720], [730, 840]], px); // 10 px between the blocks
    expect(plusAt(close, 724, 1440)).toEqual({ y: 720, from: 720, to: 780, edge: "after" });
    expect(plusAt(close, 728, 1440)).toEqual({ y: 730, from: 670, to: 730, edge: "before" });
  });

  it("on the edge of a block that touches another one", () => {
    const touching = busyBlocks([[600, 720]], px);
    expect(plusAt(touching, 604, 1440)).toEqual({ y: 600, from: 540, to: 600, edge: "before" });
    expect(plusAt(touching, 716, 1440)).toEqual({ y: 720, from: 720, to: 780, edge: "after" });
  });

  it("nothing inside a block away from its edges", () => {
    expect(plusAt(day, 1000, 1440)).toBeNull();
  });
});

describe("the plus snaps to the hour lines of a free place", () => {
  const hours = Array.from({ length: 24 }, (_, h) => ({ m: h * 60, y: h * 60 })); // an hour line per 60 px
  it("stands on the hour line nearest the pointer, for an hour or up to the next block", () => {
    expect(plusAt(day, 300, 1440, hours)).toEqual({ y: 300, from: 300, to: 360, edge: "gap" });
    expect(plusAt(day, 1130, 1440, hours)).toEqual({ y: 1140, from: 1140, to: 1200, edge: "gap" });
    expect(plusAt(day, 925, 1440, hours)).toEqual({ y: 900, from: 900, to: 960, edge: "gap" }); // 16:00 has no room: the line before it
  });
  it("on any line of an empty day", () => {
    const none = busyBlocks([], px);
    expect(plusAt(none, 1010, 1440, hours)).toEqual({ y: 1020, from: 1020, to: 1080, edge: "gap" });
    expect(plusAt(none, 100, 1440, hours)).toEqual({ y: 120, from: 120, to: 180, edge: "gap" });
  });
  it("a block's edge wins when the pointer is on it", () => {
    expect(plusAt(day, 1076, 1440, hours)).toEqual({ y: 1080, from: 1080, to: 1140, edge: "after" });
  });
});
