import { describe, expect, it } from "vitest";

import { addSet, emptyBuild, readBuild, removeSet, stoneCap, swapWeapons, withSet, writeBuild } from "./build";
import type { GearItem } from "./engine";

describe("a saved gear build", () => {
  it("reads back what was written, and a broken text gives the default build", () => {
    const b = withSet(emptyBuild(), 0, (s) => ({ ...s, slots: { main: { id: 1, enchant: 10, stones: [5, null] } } }));
    expect(readBuild(writeBuild(b))).toEqual(b);
    expect(readBuild("{oops")).toEqual(emptyBuild());
    expect(readBuild(null)).toEqual(emptyBuild());
    expect(readBuild(JSON.stringify({ ...b, level: 99, active: 7 })).level).toBe(55); // the level and the active set stay in range
  });

  it("adds a set as a copy of the active one, at most four, and removes one keeping the active set in range", () => {
    let b = withSet(emptyBuild(), 0, (s) => ({ ...s, slots: { head: { id: 2, enchant: 0, stones: [] } } }));
    b = addSet(b);
    expect(b.sets.map((s) => s.title)).toEqual(["Набор 1", "Набор 2"]);
    expect(b.sets[1].slots.head?.id).toBe(2);
    expect(b.active).toBe(1);
    b = addSet(addSet(addSet(b)));
    expect(b.sets.length).toBe(4);
    b = removeSet(b, 0);
    expect(b.sets.map((s) => s.title)).toEqual(["Набор 1", "Набор 2", "Набор 3"]);
    expect(b.active).toBe(2);
    expect(removeSet(emptyBuild(), 0).sets.length).toBe(1);
  });
});

const piece = (id: number, slot: string, grp: string) => ({ id, slot, grp } as GearItem);

describe("the weapons of a build", () => {
  const items = new Map([[1, piece(1, "main_or_sub", "sword")], [2, piece(2, "main_or_sub", "dagger")], [3, piece(3, "sub", "shield")],
    [4, piece(4, "main", "greatsword")]]);
  const slot = (id: number) => ({ id, enchant: 5, stones: [9] });

  it("swap the hands with their enchant and stones", () => {
    const swapped = swapWeapons({ main: slot(1), sub: slot(2), head: slot(7) }, items)!;
    expect(swapped.main?.id).toBe(2);
    expect(swapped.sub).toEqual(slot(1));
    expect(swapped.head?.id).toBe(7);
    expect(swapWeapons({ main: slot(1) }, items)).toEqual({ sub: slot(1) }); // one weapon goes to the empty hand
  });

  it("do not swap what cannot change hands", () => {
    expect(swapWeapons({ main: slot(4), sub: slot(3) }, items)).toBeNull(); // a two-hander is not for the off hand
    expect(swapWeapons({ main: slot(1), sub: slot(3) }, items)).toBeNull(); // a shield is not for the main hand
    expect(swapWeapons({ main: slot(4) }, items)).toBeNull();
    expect(swapWeapons({}, items)).toBeNull();
  });

  it("read the manastone cap from the card", () => {
    expect(stoneCap([{ kind: "text", text: "Можно усилить магическими камнями 70-го уровня и ниже." }])).toBe(70);
    expect(stoneCap([{ kind: "text", text: "Усиление 0/15" }])).toBeNull();
    expect(stoneCap(undefined)).toBeNull();
  });
});
