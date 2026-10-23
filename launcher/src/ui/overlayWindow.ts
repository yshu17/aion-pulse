// «В накладку»: the main window hides, a small always-on-top window in the corner of the same monitor shows the
// state and the notifications. The main window keeps watching Chat.log and sends the overlay what to show; the
// overlay sends back what the user pressed.
import { emitTo, listen, UnlistenFn } from "@tauri-apps/api/event";
import { PhysicalPosition, PhysicalSize } from "@tauri-apps/api/dpi";
import { currentMonitor, getCurrentWindow, Window } from "@tauri-apps/api/window";

import { keepInside } from "./overlayPlacement";
import { platform } from "./platform";

export const OVERLAY = "overlay";
const MAIN = "main";
const WIDTH = 380;
const MARGIN = 16;
const PLACE = "pulse-overlay-place"; // where the user put the strip: its top-left corner on the screen, physical pixels (both windows share it)

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
  game: boolean | null; // is the game process running; null when the check is off or not done yet
}

export type OverlayAction = { kind: "expand" } | { kind: "accept" | "snooze" | "dismiss" | "retry"; id: number };

/** True inside the overlay window (the same page, opened in the window labelled «overlay»). */
export const isOverlay = platform !== null && getCurrentWindow().label === OVERLAY;

/** Hide the main window and show the overlay where the user left it, or in the top-right corner of this monitor. */
export async function enterOverlay(): Promise<void> {
  const overlay = await Window.getByLabel(OVERLAY);
  if (overlay === null) return;
  let anchor = savedPlace();
  if (!anchor) {
    const area = await workArea(); // the corner of the work area: above the taskbar, not under it
    if (area) {
      const scale = await getCurrentWindow().scaleFactor();
      anchor = {
        x: area.x + area.width - Math.round((WIDTH + MARGIN) * scale),
        y: area.y + Math.round(MARGIN * scale),
      };
    }
  }
  if (anchor) {
    await overlay.setPosition(new PhysicalPosition(anchor.x, anchor.y));
    await emitTo(OVERLAY, "pulse-place", anchor); // the overlay page puts its window exactly, for the side it opens notifications to
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

export type Point = { x: number; y: number };
export const onPlace = (handler: (anchor: Point) => void): Promise<UnlistenFn> =>
  listen<Point>("pulse-place", (event) => handler(event.payload));

/**
 * Put the overlay window at (x, y), kept inside the work area (never under the taskbar), as tall as its content (`heightCss`, CSS pixels), so the empty part never covers the
 * game. With a page zoom (devicePixelRatio is not the monitor scale) CSS and window pixels differ.
 */
export async function placeWindow(x: number, y: number, heightCss: number, keepInWorkArea = true): Promise<Point> {
  const win = getCurrentWindow();
  const scale = await win.scaleFactor();
  const size = new PhysicalSize(Math.round(WIDTH * scale), Math.max(48, Math.ceil(heightCss * window.devicePixelRatio)));
  const area = await workArea();
  const origin = area && keepInWorkArea ? keepInside({ x, y }, { width: size.width, height: size.height }, area) : { x, y };
  await Promise.all([win.setPosition(new PhysicalPosition(origin.x, origin.y)), win.setSize(size)]);
  return origin; // not under the taskbar: the caller keeps the strip where the window really is
}

/** The work area of the monitor the overlay is on (physical pixels): the screen without the taskbar and docked panels. */
export interface Area { x: number; y: number; width: number; height: number }
export async function workArea(): Promise<Area | null> {
  const monitor = await currentMonitor();
  if (!monitor) return null;
  const { position, size } = monitor.workArea;
  return { x: position.x, y: position.y, width: size.width, height: size.height };
}

/** Where the overlay window is, on the screen (physical pixels). */
export async function windowPosition(): Promise<Point> {
  const position = await getCurrentWindow().outerPosition();
  return { x: position.x, y: position.y };
}

/** The monitor the overlay is on: its top and height, physical pixels. */


function savedPlace(): { x: number; y: number } | null {
  try {
    const place = JSON.parse(localStorage.getItem(PLACE) ?? "null");
    return Number.isInteger(place?.x) && Number.isInteger(place?.y) ? place : null;
  } catch {
    return null;
  }
}

/** Start moving the overlay with the mouse; the new place is kept for the next time (see saveAnchor). */
export function startDrag(): void {
  getCurrentWindow().startDragging().catch(() => {});
}

/** The window was moved (by the user or by placeWindow): its new position, physical pixels. */
export function onWindowMoved(handler: (x: number, y: number) => void): Promise<UnlistenFn> {
  return getCurrentWindow().onMoved(({ payload }) => handler(payload.x, payload.y));
}

/** Remember where the strip is, for the next time. */
export function saveAnchor(anchor: Point): void {
  try { localStorage.setItem(PLACE, JSON.stringify(anchor)); } catch { /* not kept: the corner next time */ }
}

/** How the overlay looks and behaves, kept in this computer's browser storage (both windows share it). */
export interface OverlayLook {
  opacity: number; // 0.3…1, the whole overlay; it is opaque while the mouse is over it
  keepGameFocus: boolean; // a click on the overlay leaves the keyboard with the game
  turnSec: number; // how long each of several running events stays on the line before the next one comes (2…20)
  returnWhenGameClosed: boolean; // the game is gone for a while: the overlay goes back to the main window
}

const LOOK = "pulse-overlay-look";
const DEFAULT_LOOK: OverlayLook = { opacity: 0.9, keepGameFocus: true, turnSec: 5, returnWhenGameClosed: true };

export function loadLook(): OverlayLook {
  try {
    const raw = JSON.parse(localStorage.getItem(LOOK) ?? "{}");
    const opacity = typeof raw.opacity === "number" ? Math.min(1, Math.max(0.3, raw.opacity)) : DEFAULT_LOOK.opacity;
    const turnSec = Number.isFinite(raw.turnSec) ? Math.min(20, Math.max(2, Math.round(raw.turnSec))) : DEFAULT_LOOK.turnSec;
    return {
      opacity,
      keepGameFocus: typeof raw.keepGameFocus === "boolean" ? raw.keepGameFocus : DEFAULT_LOOK.keepGameFocus,
      turnSec,
      returnWhenGameClosed: typeof raw.returnWhenGameClosed === "boolean" ? raw.returnWhenGameClosed : DEFAULT_LOOK.returnWhenGameClosed,
    };
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
