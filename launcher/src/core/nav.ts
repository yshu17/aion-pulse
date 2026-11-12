/**
 * The way back through the screens: «Назад» returns to the tab (and the section of a menu tab) the user came from.
 * A tab keeps its own place (filters, chosen row, zone, scroll) while it is alive under the others, so going back to a
 * screen is enough to find it as it was left.
 *
 *   visit(trail, from, to) -> trail      the trail after going from one screen to another (the screen left is added)
 *   back(trail) -> [screen | null, trail]  the last screen of the trail and the trail without it
 */

export const MAX_TRAIL = 40;

export function visit(trail: string[], from: string, to: string): string[] {
  if (from === to) return trail;
  const next = trail[trail.length - 1] === from ? trail : [...trail, from];
  return next.length > MAX_TRAIL ? next.slice(next.length - MAX_TRAIL) : next;
}

export function back(trail: string[]): [string | null, string[]] {
  if (!trail.length) return [null, trail];
  return [trail[trail.length - 1], trail.slice(0, -1)];
}
