import { describe, expect, it } from "vitest";

import { anchorOf, chooseSide, keepInside, windowOrigin } from "./overlayPlacement";

const H = 1080; // a 1080 p monitor starting at y = 0; a quarter is 270 px
const PILL = 36;

describe("overlay side", () => {
  it("opens notifications upwards when less than a quarter of the screen is below the strip", () => {
    expect(chooseSide(1080 - 100 - PILL, PILL, 0, H, "down")).toBe("up");
    expect(chooseSide(1080 - 270 - PILL + 1, PILL, 0, H, "down")).toBe("up"); // 269 px below: still the bottom quarter
  });

  it("opens them downwards when less than a quarter is above the strip", () => {
    expect(chooseSide(16, PILL, 0, H, "up")).toBe("down");
    expect(chooseSide(269, PILL, 0, H, "up")).toBe("down");
  });

  it("keeps the last side in the middle band, so the layout does not flip while the strip is moved", () => {
    expect(chooseSide(500, PILL, 0, H, "down")).toBe("down");
    expect(chooseSide(500, PILL, 0, H, "up")).toBe("up");
    expect(chooseSide(270, PILL, 0, H, "up")).toBe("up"); // exactly a quarter above is not «less than»
  });

  it("measures from the monitor, not from the origin of the desktop", () => {
    // a second monitor to the right and 200 px lower: its top is y = 200
    expect(chooseSide(200 + 20, PILL, 200, H, "up")).toBe("down");
    expect(chooseSide(200 + H - 60, PILL, 200, H, "down")).toBe("up");
  });
});

describe("overlay window origin", () => {
  it("puts the window so the strip stays on its screen position, whatever is above it", () => {
    const anchor = { x: 1500, y: 900 };
    const alone = windowOrigin(anchor, { left: 1, top: 1 }, 1.25); // strip at the top of the window
    const withToasts = windowOrigin(anchor, { left: 1, top: 301 }, 1.25); // 300 px of notifications above it
    expect(alone).toEqual({ x: 1499, y: 899 });
    expect(withToasts).toEqual({ x: 1499, y: 524 });
    expect(anchorOf(withToasts, { left: 1, top: 301 }, 1.25)).toEqual(anchor); // and back
  });
});

describe("overlay inside the work area", () => {
  // a 1920x1080 monitor with a 40 px taskbar at the bottom: the work area is 1040 px high
  const area = { x: 0, y: 0, width: 1920, height: 1040 };
  const size = { width: 380, height: 102 };

  it("keeps a window that would go under the taskbar above it", () => {
    expect(keepInside({ x: 1500, y: 1000 }, size, area)).toEqual({ x: 1500, y: 938 });
    expect(keepInside({ x: 1500, y: 900 }, size, area)).toEqual({ x: 1500, y: 900 }); // already inside: untouched
  });

  it("keeps a window that was dragged past an edge inside, and a window taller than the area at the top", () => {
    expect(keepInside({ x: 2000, y: -50 }, size, area)).toEqual({ x: 1540, y: 0 });
    expect(keepInside({ x: 0, y: 0 }, { width: 380, height: 1200 }, area)).toEqual({ x: 0, y: 0 });
  });
});
