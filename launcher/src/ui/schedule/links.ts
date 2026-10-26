// Links of the schedule tab: the knowledge base article built in, and the user's own (links.json next to config.json).
import { ARTICLE } from "../../core/schedule/scheduleUpdate";

export interface SavedLink {
  name: string;
  url: string;
}

export const BUILT_IN_LINK: SavedLink = { name: "Расписание в базе знаний", url: ARTICLE };
export const LINKS_FILE = "links.json";
const MAX_NAME = 60;

/** The address as a web link, or null: only http and https may be opened from the program. */
export function webAddress(text: string): string | null {
  try {
    const url = new URL(text.trim());
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch {
    return null;
  }
}

/** The user's links from the file text; a broken file or a broken entry is dropped, never an error. */
export function parseLinks(text: string | null): SavedLink[] {
  try {
    const data: unknown = text ? JSON.parse(text) : [];
    if (!Array.isArray(data)) return [];
    return data.flatMap((item: { name?: unknown; url?: unknown }) => {
      const url = typeof item?.url === "string" ? webAddress(item.url) : null;
      const name = typeof item?.name === "string" ? item.name.trim().slice(0, MAX_NAME) : "";
      return url && name ? [{ name, url }] : [];
    });
  } catch {
    return [];
  }
}

/** The name for a new link: what the user typed, else the host of the address. */
export function linkName(typed: string, url: string): string {
  return (typed.trim() || new URL(url).hostname).slice(0, MAX_NAME);
}
