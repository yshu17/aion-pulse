import { describe, expect, it } from "vitest";

import { addSet, emptyBuild, putItem, readBuild, removeSet, stoneCap, subBlocked, swapWeapons, withSet, writeBuild } from "./build";
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

  it("keeps the food and drinks of each set, copies them into a new set and drops what is no id", () => {
    const b = withSet(emptyBuild(), 0, (s) => ({ ...s, consumables: { food: 160000001, drink: 5 } }));
    expect(readBuild(writeBuild(b)).sets[0].consumables).toEqual({ food: 160000001, drink: 5 });
    const two = addSet(b);
    expect(two.sets[1].consumables).toEqual({ food: 160000001, drink: 5 });
    expect(two.sets[1].consumables).not.toBe(two.sets[0].consumables);
    const broken = JSON.stringify({ ...b, sets: [{ title: "x", slots: {}, consumables: { food: "1", candy: 7, other: 3 } }] });
    expect(readBuild(broken).sets[0].consumables).toEqual({ candy: 7 });
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

describe("a two-handed weapon fills both hands", () => {
  const items = new Map<number, GearItem>([
    [1, { ...piece(1, "main_or_sub", "sword"), stones: 3 } as GearItem], [3, { ...piece(3, "sub", "shield"), stones: 2 } as GearItem],
    [4, { ...piece(4, "main", "greatsword"), stones: 4 } as GearItem], [5, { ...piece(5, "wing", "wing"), stones: 2 } as GearItem],
    [6, { ...piece(6, "main", "orb"), stones: 4 } as GearItem],
  ]);
  const at = (id: number) => ({ id, enchant: 5, stones: [9] });

  it("empties the off hand when it goes to the main hand, and blocks the off hand while it is there", () => {
    const slots = { main: at(1), sub: at(3), head: at(7) };
    const two = putItem(slots, "main", items.get(4)!, items)!;
    expect(two.sub).toBeUndefined();
    expect(two.main).toEqual({ id: 4, enchant: 0, stones: [null, null, null, null] });
    expect(two.head?.id).toBe(7);
    expect(subBlocked(two, items)).toBe(true);
    expect(putItem(two, "sub", items.get(3)!, items)).toBeNull(); // no shield, no second weapon
    expect(putItem(two, "sub", items.get(1)!, items)).toBeNull();
    expect(subBlocked({ main: at(6) }, items)).toBe(true); // a spellbook or an orb fills both hands too
  });

  it("leaves the off hand free for a one-hander, and frees it again when the main hand changes", () => {
    const one = putItem({ main: at(1) }, "sub", items.get(3)!, items)!;
    expect(one.sub?.id).toBe(3);
    expect(subBlocked(one, items)).toBe(false);
    expect(putItem(one, "main", items.get(1)!, items)!.sub?.id).toBe(3); // a one-hander keeps the shield
    expect(subBlocked({ main: at(4) }, new Map())).toBe(false); // an item that is not known blocks nothing
  });

  it("gives an item that takes no manastones none, whatever its card says", () => {
    expect(putItem({}, "wing", items.get(5)!, items)!.wing?.stones).toEqual([]);
  });
});
