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

/**
 * What the «Карта» tab is asked to show — one way in for the chat and for the cards of the program:
 *   place  a «Место» link of the chat: its card is «Место из чата»
 *   npc    an NPC or a monster by its id (data/maps/spawns.json) in a zone: all its points there, `at` (game x, y) picks
 *          the one to centre on (the nearest point), else the first; `points` (game x, y, z) are the caller's own points of the NPC in
 *          that zone, drawn when spawns.json has none under this id (the bestiary's duplicate records of one name keep their places that way)
 *   zone   a zone by its map_id: its map, nothing picked
 */
export type MapTarget = ({ type: "place" } & ChatPlace) | { type: "npc"; npc: string; name: string; map_id: string; at?: [number, number]; points?: [number, number, number][] }
  | { type: "zone"; map_id: string };

/** A thing a card names, opened where it lives: an item, a quest or a title in «База данных», an NPC in «NPC», a zone on «Карта». */
export interface CardRef { kind: "item" | "quest" | "title" | "npc" | "zone"; id: string; name: string }
export const OpenRef = createContext<((ref: CardRef) => void) | null>(null);
export const useOpenRef = () => useContext(OpenRef);

/** Opens something on the map (the «Карта» tab). */
export const OpenMap = createContext<((target: MapTarget) => void) | null>(null);
export const useOpenMap = () => useContext(OpenMap);

/** Opens a place from the chat on the map (the «Карта» tab). */
export const OpenPlace = createContext<((place: ChatPlace) => void) | null>(null);
export const useOpenPlace = () => useContext(OpenPlace);

/** A message as plain text: item and place links as their names («<Место · Келькмарос>» -> «Место · Келькмарос»). */
export function plainMessage(text: string): string {
  return messageSegments(text).map((s) => (s.kind === "text" ? s.text : s.text.slice(1, -1))).join("");
}
