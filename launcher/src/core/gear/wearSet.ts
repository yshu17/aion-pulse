/**
 * «Надеть комплект»: every piece of an item set into its slot of the doll at once. Pure.
 *
 *   const plan = planSet(slots, setItems, itemsById, cls)
 *     plan.puts     the missing pieces and the slot each goes to (worn pieces stay as they are, with enchant and stones)
 *     plan.removed  what would come off: the slot's item, and a hand a two-hander (or a shield) cannot share
 *     plan.cannot   pieces the class cannot wear
 *   applySet(slots, plan, onlyFree?) -> new slots   onlyFree skips every piece that would take something off
 */
import type { SavedSet, SavedSlot } from "./build";
import { isTwoHanded, stoneSlots, type GearItem, type SlotKey } from "./engine";

export interface SetPut { slot: SlotKey; item: GearItem; takes: { slot: SlotKey; id: number }[] }
export interface SetPlan { puts: SetPut[]; removed: { slot: SlotKey; id: number }[]; cannot: GearItem[] }

type Slots = SavedSet["slots"];

/** The doll slots an item may go to, the preferred first. */
function slotsOf(item: GearItem): SlotKey[] {
  if (item.slot === "main" || item.slot === "main_or_sub") return ["main", ...(item.slot === "main_or_sub" ? ["sub" as SlotKey] : [])];
  if (item.slot === "sub") return ["sub"];
  if (item.slot === "earring") return ["earring1", "earring2"];
  if (item.slot === "ring") return ["ring1", "ring2"];
  return [item.slot as SlotKey];
}

export function planSet(slots: Slots, setItems: GearItem[], items: ReadonlyMap<number, GearItem>, cls: string): SetPlan {
  const wornIds = new Set(Object.values(slots).map((s) => s!.id));
  const setIds = new Set(setItems.map((i) => i.id));
  const cannot = setItems.filter((i) => !wornIds.has(i.id) && i.classes.length > 0 && !i.classes.includes(cls));
  // weapons that fit only the main hand first, so a one-hander and a shield never fight over a hand
  const wanted = setItems.filter((i) => !wornIds.has(i.id) && !cannot.includes(i)).sort((a, b) => slotsOf(a).length - slotsOf(b).length);
  const taken = new Set<SlotKey>(Object.entries(slots).filter(([, s]) => setIds.has(s!.id)).map(([k]) => k as SlotKey));
  const puts: SetPut[] = [];
  for (const item of wanted) {
    const options = slotsOf(item).filter((s) => !taken.has(s));
    const slot = options.find((s) => !slots[s]) ?? options[0];
    if (!slot) continue;
    taken.add(slot);
    const takes: SetPut["takes"] = slots[slot] ? [{ slot, id: slots[slot]!.id }] : [];
    if (slot === "main" && isTwoHanded(item) && slots.sub) takes.push({ slot: "sub", id: slots.sub.id });
    const main = slots.main && items.get(slots.main.id);
    if (slot === "sub" && main && isTwoHanded(main)) takes.push({ slot: "main", id: slots.main!.id });
    puts.push({ slot, item, takes });
  }
  const removed = [...new Map(puts.flatMap((p) => p.takes).map((t) => [t.slot, t])).values()];
  return { puts, removed, cannot };
}

export function applySet(slots: Slots, plan: SetPlan, onlyFree = false): Slots {
  const out: Slots = { ...slots };
  const chosen = onlyFree ? plan.puts.filter((p) => !p.takes.length) : plan.puts;
  for (const put of chosen) for (const t of put.takes) if (out[t.slot]?.id === t.id) delete out[t.slot];
  for (const put of chosen) {
    const saved: SavedSlot = { id: put.item.id, enchant: 0, stones: Array(stoneSlots(put.item)).fill(null) };
    out[put.slot] = saved;
  }
  return out;
}
