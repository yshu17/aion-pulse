// The item card's own window («card» in tauri.conf.json): a click in the chat sends it the item and the place of the
// click on the screen; it may stand anywhere on the screen, not only inside the program's window.
import { emitTo, listen, UnlistenFn } from "@tauri-apps/api/event";
import { cursorPosition, getCurrentWindow } from "@tauri-apps/api/window";

import { platform } from "./platform";

export const CARD = "card";

/** An item to show and where the click was: physical pixels of the screen. */
export interface CardOpen { id: string; x: number; y: number }

/** True inside the card's window (the same page, opened in the window labelled «card»). */
export const isCard = platform !== null && getCurrentWindow().label === CARD;

/** Open the card of an item next to the mouse pointer (the click), or `at` (physical screen pixels) when given. */
export async function openCardWindow(id: string, at?: { x: number; y: number }): Promise<void> {
  const point = at ?? await cursorPosition().catch(() => null);
  const x = point?.x ?? Math.round(window.screenX * window.devicePixelRatio);
  const y = point?.y ?? Math.round(window.screenY * window.devicePixelRatio);
  await emitTo(CARD, "card-open", { id, x, y } satisfies CardOpen);
}

export const closeCardWindow = () => emitTo(CARD, "card-close", null).catch(() => {});

export const onCardOpen = (handler: (open: CardOpen) => void): Promise<UnlistenFn> =>
  listen<CardOpen>("card-open", (event) => handler(event.payload));
export const onCardClose = (handler: () => void): Promise<UnlistenFn> => listen("card-close", () => handler());
