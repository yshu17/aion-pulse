/**
 * Packed id lists of pulse.db (core/pulse_db/build.py pack_ids): an NPC's drops (npc.drops, in the card's order) and the
 * NPCs that drop an item (item.dropped_by, sorted, kept as steps). 2.5 million links take ~14 MB this way instead of
 * ~74 MB as a link table with its index; they are read on exactly these two paths.
 *
 * Each id is 7 bits a byte, low bits first, the high bit set while more bytes follow. The program's db_query gives a
 * BLOB as a list of numbers, sql.js as a Uint8Array: both are read.
 */
export function unpackIds(bytes: ArrayLike<number> | null | undefined, delta = false): number[] {
  const out: number[] = [];
  if (!bytes) return out;
  let value = 0;
  let shift = 0;
  let previous = 0;
  for (let i = 0; i < bytes.length; i++) {
    const byte = bytes[i];
    value += (byte & 0x7f) * 2 ** shift; // not «<<»: ids may pass 2^31
    if (byte & 0x80) {
      shift += 7;
      continue;
    }
    previous = delta ? previous + value : value;
    out.push(previous);
    value = shift = 0;
  }
  return out;
}
