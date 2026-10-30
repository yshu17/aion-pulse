// A place from the chat («<Место · Келькмарос>» with coordinates) and the way the chat opens it on the map.
import { createContext, useContext } from "react";

import { messageSegments } from "../../core/chat/segments";
import type { Place } from "../../core/map/zones";

/** A place link of a chat message: where (game coordinates), its name, and who wrote it when. */
export interface ChatPlace extends Place {
  nick: string;
  time: string; // «HH:MM:SS»
  text: string; // the whole message, links as their names
}

/** Opens a place from the chat on the map (the «Карта» tab). */
export const OpenPlace = createContext<((place: ChatPlace) => void) | null>(null);
export const useOpenPlace = () => useContext(OpenPlace);

/** A message as plain text: item and place links as their names («<Место · Келькмарос>» -> «Место · Келькмарос»). */
export function plainMessage(text: string): string {
  return messageSegments(text).map((s) => (s.kind === "text" ? s.text : s.text.slice(1, -1))).join("");
}
