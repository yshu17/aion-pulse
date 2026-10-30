/**
 * The item card (the description shown by a click on an item in the chat): which item a link is, the grade colour
 * and the layout of the description blocks — the same layout as Pulse's watcher/tooltip.py. Pure: no files, no DOM.
 */

import type { Segment } from "../chat/segments";

export type Block = Record<string, any>; // one block of a description: kind pairs, props, warning, hr, grid, text, stones, set, recipe

/**
 * The item id of each segment (null for text and places). A chat link carries its item's own id, and several items
 * share one name (a link's text is only the name: a quest «Золотая медаль» and the reward one), so each item segment
 * takes the first unused id of the message's links that has this name, even one without a description (the caller
 * then shows no card, not the card of another item); with no such link, the id its name stands for.
 */
export function segmentItemIds(segments: Segment[], linkIds: string[], names: Record<string, string>): (string | null)[] {
  const left = [...linkIds];
  return segments.map((segment) => {
    if (segment.kind !== "item") return null;
    const name = segment.text.slice(1, -1); // «<Name>»
    const at = left.findIndex((id) => names[id] === name);
    return at >= 0 ? left.splice(at, 1)[0] : segment.item_id;
  });
}

/** The grade of the card's name colour, lower case («Unique» in some descriptions); the catalog's when the spec has none. */
export function cardGrade(specGrade: string | undefined, catalogGrade = ""): string {
  return (specGrade || catalogGrade || "common").toLowerCase();
}

// stats the descriptions keep in tenths of a percent («+52» is +5.2 %), as the game shows them
const TENTHS = new Set(["Агрессия", "Защита в ПвП", "Урон в ПвП"]);

/**
 * A stat's value as the game writes it: a minus is stored as «+-16%» and reads «-16%»; the tenths stats get their
 * decimal point and percent sign («+50%» -> «+5.0%», «+-16%» -> «-1.6%», «+52» -> «+5.2%»). Other values stay.
 */
export function statValue(label: string, value: string): string {
  const plain = value.replace(/^\+-/, "-");
  if (!TENTHS.has(label)) return plain;
  const match = /^([+-]?)(\d+)%?$/.exec(plain.trim());
  if (!match) return plain;
  return `${match[1] || "+"}${(Number(match[2]) / 10).toFixed(1)}%`;
}

/** The leading pairs, properties and warning go beside the picture, the rest under it (as in Pulse). */
export function headBlocks(blocks: Block[]): [Block[], Block[]] {
  let split = 0;
  while (split < blocks.length && ["pairs", "props", "warning"].includes(blocks[split].kind)) split++;
  return [blocks.slice(0, split), blocks.slice(split)];
}
