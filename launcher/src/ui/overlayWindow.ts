// «В накладку»: the main window hides, a small always-on-top window in the corner of the same monitor shows the
// state and the notifications. The main window keeps watching Chat.log and sends the overlay what to show; the
// overlay sends back what the user pressed.
import { emitTo, listen, UnlistenFn } from "@tauri-apps/api/event";
import { LogicalSize, PhysicalPosition } from "@tauri-apps/api/dpi";
import { currentMonitor, getCurrentWindow, Window } from "@tauri-apps/api/window";

import { platform } from "./platform";

export const OVERLAY = "overlay";
const MAIN = "main";
const WIDTH = 380;
const MARGIN = 16;

export interface OverlayToast {
  id: number;
  title: string;
  text: string;
  icon: string | null;
  accept: boolean;
}

export interface OverlayState {
  watching: boolean;
  problem: string; // empty when Chat.log is read
  counters: [number, number, number];
  toasts: OverlayToast[];
}

export type OverlayAction = { kind: "expand" } | { kind: "accept" | "snooze" | "dismiss"; id: number };

/** True inside the overlay window (the same page, opened in the window labelled «overlay»). */
export const isOverlay = platform !== null && getCurrentWindow().label === OVERLAY;

/** Hide the main window and show the overlay in the top-right corner of the monitor the main window is on. */
export async function enterOverlay(): Promise<void> {
  const overlay = await Window.getByLabel(OVERLAY);
  if (overlay === null) return;
  const monitor = await currentMonitor();
  if (monitor) {
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
  getCurrentWindow().setSize(new LogicalSize(WIDTH, Math.max(48, Math.ceil(height)))).catch(() => {});
}
