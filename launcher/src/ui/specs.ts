// An item's description for its card, from the game database (pulse.db item.spec, core/db/items.ts).
import { itemSpecs } from "../core/db/items";
import type { Spec } from "../core/items/specs";
import { pulseDb } from "./db/pulseDb";

export type SpecAnswer = { spec: Spec | null; error?: string };

let reader: Promise<((id: string) => Promise<Spec | null>) | null> | null = null;

/** The description of an item, or null (with the error when the database could not be read). */
export async function itemSpec(id: string): Promise<SpecAnswer> {
  reader ??= pulseDb().then((all) => all && itemSpecs(all));
  try {
    const read = await reader;
    if (!read) return { spec: null, error: "нет базы игры data/pulse.db" };
    return { spec: await read(id) };
  } catch (error) {
    reader = null; // the next card tries again
    return { spec: null, error: String(error) };
  }
}
