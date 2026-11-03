import { describe, expect, it } from "vitest";

import { unpackIds } from "./packed";

describe("packed id lists of pulse.db (core/pulse_db/build.py pack_ids)", () => {
  it("reads ids in their order, 7 bits a byte, the high bit for «more»", () => {
    expect(unpackIds([0x01, 0x64])).toEqual([1, 100]);
    expect(unpackIds(new Uint8Array([0xe7, 0xeb, 0x93, 0x4f]))).toEqual([166000103]); // a real item id, four bytes
  });

  it("reads a sorted list kept as steps from the previous id", () => {
    expect(unpackIds([0x64, 0x05, 0x01], true)).toEqual([100, 105, 106]);
  });

  it("reads nothing as an empty list, also a missing value", () => {
    expect(unpackIds([])).toEqual([]);
    expect(unpackIds(null)).toEqual([]);
  });
});
