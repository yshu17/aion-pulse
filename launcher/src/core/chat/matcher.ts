/**
 * Keyword search over chat messages — the port of core/chat/matcher.py (step 3 completes it).
 * For now: `normalize`, shared with the item list search.
 */

/** Lower case and «ё» as «е». Keeps the string length. */
export function normalize(text: string): string {
  return text.toLowerCase().replace(/ё/g, "е");
}
