/**
 * Broken texts some item cards of pulse.db carry (the site's cards the builder could not repair: food, scrolls). Pure.
 *
 *   cleanCardText("Маг. защита% +5. ElementalDefendAll% +10. Время полета% +.")
 *     -> "Маг. защита +5. Защ. от стихий +10. Время полета: значение в клиенте не указано."
 *   cleanCard(spec | null) -> the card with its text blocks cleaned
 *
 *   «name% +5»: the «%» before the plus is the site's leftover, the number is a flat one (the same foods without it give
 *     the same numbers); a real percent stands after the number («+9%») and stays
 *   «ElementalDefendAll»: the client's key, «Защ. от стихий» in the game's cards
 *   «name +.»: a bonus the client holds no number for
 */
import type { Spec } from "./specs";

export function cleanCardText(text: string): string {
  return String(text)
    .split("ElementalDefendAll").join("Защ. от стихий")
    .replace(/(?<=[A-Za-zА-Яа-яЁё.])%(?= \+)/g, "")
    .replace(/([А-ЯЁA-Z][^.+]*?) \+(\.|$)/g, "$1: значение в клиенте не указано.");
}

export function cleanCard<T extends Spec | null>(card: T): T {
  const blocks = (card as { blocks?: { kind?: string; text?: string }[] } | null)?.blocks;
  if (!card || !blocks) return card;
  return { ...card, blocks: blocks.map((b) => (b.kind === "text" && b.text ? { ...b, text: cleanCardText(b.text) } : b)) } as T;
}
