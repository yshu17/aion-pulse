import { describe, expect, it } from "vitest";

import { gameStep } from "./gameWatch";

describe("game check", () => {
  it("stops and warns once when the game is gone, clears when it is back, never acts on an unknown answer", () => {
    // running, enabled, watching, warned
    expect(gameStep(false, true, true, false)).toEqual({ stop: true, warn: true, clear: false });
    expect(gameStep(false, true, true, true)).toEqual({ stop: true, warn: false, clear: false }); // already warned
    expect(gameStep(false, true, false, false)).toEqual({ stop: false, warn: true, clear: false }); // not watching: warn only
    expect(gameStep(true, true, true, true)).toEqual({ stop: false, warn: false, clear: true });
    expect(gameStep(true, true, true, false)).toEqual({ stop: false, warn: false, clear: false });
    expect(gameStep(null, true, true, true)).toEqual({ stop: false, warn: false, clear: true }); // unreadable list: no stop
    expect(gameStep(null, true, true, false)).toEqual({ stop: false, warn: false, clear: false });
    expect(gameStep(false, false, true, true)).toEqual({ stop: false, warn: false, clear: true }); // check switched off
    expect(gameStep(false, false, true, false)).toEqual({ stop: false, warn: false, clear: false });
  });
});
