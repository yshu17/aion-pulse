// Where the notifications of the overlay open: below the one-line strip, or above it when the strip is near the
// bottom of the screen. Pure arithmetic in physical pixels, so it can be tested without a window.

export type Side = "up" | "down";

/** Which part of the monitor height counts as «near an edge». */
export const EDGE = 0.25;

/**
 * The side the notifications open to for a strip at `pillTop` (screen pixels, `pillHeight` tall) on a monitor
 * that starts at `monitorTop` and is `monitorHeight` tall.
 *  - less than 25 % of the screen height under the strip: upwards;
 *  - less than 25 % above it: downwards;
 *  - in the middle band: as before (`current`), so the layout does not flip while the strip is moved around.
 */
export function chooseSide(pillTop: number, pillHeight: number, monitorTop: number, monitorHeight: number, current: Side): Side {
  const below = monitorTop + monitorHeight - (pillTop + pillHeight);
  const above = pillTop - monitorTop;
  if (below < monitorHeight * EDGE) return "up";
  if (above < monitorHeight * EDGE) return "down";
  return current;
}

/**
 * Is the strip (its top-left corner `anchor`, `size` in physical pixels) on some screen? A place saved with another
 * monitor layout (a monitor unplugged, the resolution changed) can lie outside every screen: the strip is then not
 * visible at all. The strip counts as visible when its centre is inside a monitor.
 */
export function onScreen(anchor: { x: number; y: number }, size: { width: number; height: number }, monitors: { x: number; y: number; width: number; height: number }[]): boolean {
  const cx = anchor.x + size.width / 2;
  const cy = anchor.y + size.height / 2;
  return monitors.some((m) => cx >= m.x && cx < m.x + m.width && cy >= m.y && cy < m.y + m.height);
}

/**
 * The window origin moved, if needed, so the whole window (`size`, physical pixels) lies inside `area`: the taskbar and
 * docked panels are not part of the work area, so the overlay is never placed under them.
 */
export function keepInside(origin: { x: number; y: number }, size: { width: number; height: number }, area: { x: number; y: number; width: number; height: number }): { x: number; y: number } {
  const maxX = Math.max(area.x, area.x + area.width - size.width);
  const maxY = Math.max(area.y, area.y + area.height - size.height);
  return { x: Math.min(Math.max(origin.x, area.x), maxX), y: Math.min(Math.max(origin.y, area.y), maxY) };
}

/**
 * The window position that keeps the strip where the user put it. `anchor` is the strip's top-left corner on the
 * screen; `inside` is where the strip's corner is within the window (CSS pixels), which depends on the side: with
 * notifications above it the strip is lower in the window.
 */
export function windowOrigin(anchor: { x: number; y: number }, inside: { left: number; top: number }, dpr: number): { x: number; y: number } {
  return { x: Math.round(anchor.x - inside.left * dpr), y: Math.round(anchor.y - inside.top * dpr) };
}

/** The strip's top-left corner on the screen, from the window position and where the strip is in the window. */
export function anchorOf(window: { x: number; y: number }, inside: { left: number; top: number }, dpr: number): { x: number; y: number } {
  return { x: Math.round(window.x + inside.left * dpr), y: Math.round(window.y + inside.top * dpr) };
}
