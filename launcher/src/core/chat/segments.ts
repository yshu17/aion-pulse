/**
 * How a cleaned chat message is drawn: plain text, item links, place links and the matched words — the port of
 * core/chat/segments.py.
 *
 *   text   plain text; `hit` marks a matched keyword
 *   item   «<Name>» of an item link; item_id and grade when the item has a tooltip, hit when it matched
 *   place  «<Место · Келькмарос>»; place = [map id, game x, game y] when the link carries coordinates
 * An item link without a tooltip stays plain text, except names with «Рудр».
 */

import { highlightSegments, normalize } from "./matcher";
import { LINK_CLOSE, LINK_OPEN, Place3, splitPlace } from "./parser";

export const LINKS = new RegExp(`\\[([^\\[\\]]+)\\]|${LINK_OPEN}([^${LINK_OPEN}${LINK_CLOSE}]+)${LINK_CLOSE}`, "g");
export const HIGHLIGHT_NAMES = /рудр/i;

export interface Segment {
  text: string;
  kind: "text" | "item" | "place";
  hit: boolean;
  item_id: string | null;
  grade: string | null;
  place: Place3 | null;
}

const seg = (text: string, kind: Segment["kind"] = "text", hit = false, itemId: string | null = null,
             grade: string | null = null, place: Place3 | null = null): Segment =>
  ({ text, kind, hit, item_id: itemId, grade, place });

function plainPart(chunk: string, hits: string[]): Segment[] {
  if (!hits.length) return [seg(chunk)];
  const pieces = highlightSegments(chunk, hits).map(([piece, isHit]) => seg(piece, "text", isHit));
  return pieces.length ? pieces : [seg("")];
}

/** Segments of a message in order. specItems: item name -> id (items with a tooltip); grades: id -> grade. */
export function messageSegments(message: string, hits: string[] | null = null,
                                specItems: Record<string, string> | null = null,
                                grades: Record<string, string> | null = null): Segment[] {
  const h = hits ?? [];
  const spec = specItems ?? {};
  const grade = grades ?? {};
  const out: Segment[] = [];
  let pos = 0;
  for (const match of message.matchAll(LINKS)) {
    const start = match.index!;
    if (match[1] === undefined) { // place / quest / «where» link
      out.push(...plainPart(message.slice(pos, start), h));
      const [shown, place] = splitPlace(match[2]);
      out.push(seg(`<${shown}>`, "place", false, null, null, place));
      pos = start + match[0].length;
      continue;
    }
    const name = match[1];
    const itemId = Object.prototype.hasOwnProperty.call(spec, name) ? spec[name] : null;
    if (itemId === null && !HIGHLIGHT_NAMES.test(name)) continue; // stays in the plain text around it
    out.push(...plainPart(message.slice(pos, start), h));
    const hit = h.some((x) => x.trim() !== "" && normalize(name).includes(normalize(x)));
    out.push(seg(`<${name}>`, "item", hit, itemId, itemId !== null ? grade[itemId] ?? null : null));
    pos = start + match[0].length;
  }
  out.push(...plainPart(message.slice(pos), h));
  return out;
}
