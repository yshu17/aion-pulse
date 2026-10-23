// «В накладку»: the main window hides, a small always-on-top window in the corner of the same monitor shows the
// state and the notifications. The main window keeps watching Chat.log and sends the overlay what to show; the
// overlay sends back what the user pressed.
import { emitTo, listen, UnlistenFn } from "@tauri-apps/api/event";
import { PhysicalPosition, PhysicalSize } from "@tauri-apps/api/dpi";
import { currentMonitor, getCurrentWindow, Window } from "@tauri-apps/api/window";

import { platform } from "./platform";

export const OVERLAY = "overlay";
const MAIN = "main";
const WIDTH = 380;
const MARGIN = 16;
const PLACE = "pulse-overlay-place"; // where the user dragged the overlay to, in physical pixels (both windows share it)

export interface OverlayToast {
  id: number;
  title: string;
  text: string;
  icon: string | null;
  accept: boolean;
  retry: boolean; // «Проверить снова» (the game is not running)
}

/** One schedule event on the overlay: times are MSK «HH:MM», `left` is «ещё 38 мин» / «через 2 ч». */
export interface OverlayEvent {
  name: string;
  tone: string;
  from: string;
  to: string;
  left: string;
  progress: number | null; // how much of a running event has passed, 0…1; null for the next one
}

export interface OverlayState {
  watching: boolean;
  problem: string; // empty when Chat.log is read
  counters: [number, number, number];
  toasts: OverlayToast[];
  schedule: { current: OverlayEvent[]; next: OverlayEvent | null };
}

export type OverlayAction = { kind: "expand" } | { kind: "accept" | "snooze" | "dismiss" | "retry"; id: number };

/** True inside the overlay window (the same page, opened in the window labelled «overlay»). */
export const isOverlay = platform !== null && getCurrentWindow().label === OVERLAY;

/** Hide the main window and show the overlay in the top-right corner of the monitor the main window is on. */
export async function enterOverlay(): Promise<void> {
  const overlay = await Window.getByLabel(OVERLAY);
  if (overlay === null) return;
  const monitor = await currentMonitor();
  const place = savedPlace();
  if (place) await overlay.setPosition(new PhysicalPosition(place.x, place.y));
  else if (monitor) {
    const x = monitor.position.x + monitor.size.width - Math.round((WIDTH + MARGIN) * monitor.scaleFactor);
    const y = monitor.position.y + Math.round(MARGIN * monitor.scaleFactor);
    await overlay.setPosition(new PhysicalPosition(x, y));
  }
  await overlay.show();
  await getCurrentWindow().hide();
}

/** Back to the main window. */
export async function leaveOverlay(): Promise<void> {
  const [overlay, main] = await Promise.all([Window.getByLabel(OVERLAY), Window.getByLabel(MAIN)]);
  await overlay?.hide();
  if (main) {
    await main.show();
    await main.unminimize();
    await main.setFocus();
  }
}

export const sendState = (state: OverlayState) => emitTo(OVERLAY, "pulse-state", state);
export const onState = (handler: (state: OverlayState) => void): Promise<UnlistenFn> =>
  listen<OverlayState>("pulse-state", (event) => handler(event.payload));
export const sendAction = (action: OverlayAction) => emitTo(MAIN, "overlay-action", action);
export const onAction = (handler: (action: OverlayAction) => void): Promise<UnlistenFn> =>
  listen<OverlayAction>("overlay-action", (event) => handler(event.payload));

/** The overlay window as tall as its content, so the empty part never covers the game. */
export function fitHeight(height: number): void {
  // `height` is in CSS pixels: with a page zoom (devicePixelRatio is not the monitor scale) they differ from the window's
  const win = getCurrentWindow();
  win.scaleFactor().then((scale) => win.setSize(new PhysicalSize(Math.round(WIDTH * scale), Math.max(48, Math.ceil(height * window.devicePixelRatio)))))
    .catch(() => {});
}

function savedPlace(): { x: number; y: number } | null {
  try {
    const place = JSON.parse(localStorage.getItem(PLACE) ?? "null");
    return Number.isInteger(place?.x) && Number.isInteger(place?.y) ? place : null;
  } catch {
    return null;
  }
}

/** Start moving the overlay with the mouse; the new place is kept for the next time (see keepPlace). */
export function startDrag(): void {
  getCurrentWindow().startDragging().catch(() => {});
}

/** Remember every place the overlay is moved to. */
export function keepPlace(): Promise<UnlistenFn> {
  return getCurrentWindow().onMoved(({ payload }) => {
    try { localStorage.setItem(PLACE, JSON.stringify({ x: payload.x, y: payload.y })); } catch { /* not kept: the corner next time */ }
  });
}

/** How the overlay looks and behaves, kept in this computer's browser storage (both windows share it). */
export interface OverlayLook {
  opacity: number; // 0.3…1, the whole overlay; it is opaque while the mouse is over it
  keepGameFocus: boolean; // a click on the overlay leaves the keyboard with the game
  turnSec: number; // how long each of several running events stays on the line before the next one comes (2…20)
}

const LOOK = "pulse-overlay-look";
const DEFAULT_LOOK: OverlayLook = { opacity: 0.9, keepGameFocus: true, turnSec: 5 };

export function loadLook(): OverlayLook {
  try {
    const raw = JSON.parse(localStorage.getItem(LOOK) ?? "{}");
    const opacity = typeof raw.opacity === "number" ? Math.min(1, Math.max(0.3, raw.opacity)) : DEFAULT_LOOK.opacity;
    const turnSec = Number.isFinite(raw.turnSec) ? Math.min(20, Math.max(2, Math.round(raw.turnSec))) : DEFAULT_LOOK.turnSec;
    return { opacity, keepGameFocus: typeof raw.keepGameFocus === "boolean" ? raw.keepGameFocus : DEFAULT_LOOK.keepGameFocus, turnSec };
  } catch {
    return DEFAULT_LOOK;
  }
}

export function saveLook(look: OverlayLook): void {
  try { localStorage.setItem(LOOK, JSON.stringify(look)); } catch { /* the default next time */ }
}

/** A window that cannot take focus: clicks on it leave the keyboard with the game. */
export function setKeepGameFocus(keep: boolean): void {
  getCurrentWindow().setFocusable(!keep).catch(() => {});
}
