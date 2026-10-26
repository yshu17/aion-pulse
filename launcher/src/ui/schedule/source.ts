// Where the schedule is checked: a link the user can change (schedule_source.json next to config.json).
// The default is the knowledge base article; `known` is the fingerprint of what the schedule of the program was made
// from, and the checks compare the link with it.
import { ARTICLE } from "../../core/schedule/scheduleUpdate";

export interface Source {
  url: string;
  known: string | null; // null: the state of the link has not been taken yet
}

export const SOURCE_FILE = "schedule_source.json";
export const DEFAULT_SOURCE: Source = { url: ARTICLE, known: null };

const LOCAL_SUFFIXES = [".local", ".localhost", ".internal", ".lan", ".home", ".arpa"];

/** A public site name: not an IP address, not this computer, not a name of a local network (as the Rust side checks too). */
function publicHost(host: string): boolean {
  const name = host.toLowerCase();
  if (!name.includes(".") || name.includes(":") || name.startsWith("[") || /^[\d.]+$/.test(name) || name === "localhost") return false;
  return !LOCAL_SUFFIXES.some((suffix) => name.endsWith(suffix));
}

/** The address as a link the program may ask: https to a public site (the same rule as the Rust side). */
export function webAddress(text: string): string | null {
  try {
    const url = new URL(text.trim());
    return url.protocol === "https:" && !url.username && !url.password && publicHost(url.hostname) ? url.href : null;
  } catch {
    return null;
  }
}

/** The source from the file text; a missing or broken file is the default article. */
export function parseSource(text: string | null): Source {
  try {
    const data: { url?: unknown; known?: unknown } | null = text ? JSON.parse(text) : null;
    const url = typeof data?.url === "string" ? webAddress(data.url) : null;
    if (!url) return DEFAULT_SOURCE;
    return { url, known: typeof data?.known === "string" && data.known ? data.known : null };
  } catch {
    return DEFAULT_SOURCE;
  }
}

export const serializeSource = (source: Source): string => JSON.stringify(source, null, 1) + "\n";

/**
 * What a check compares the link with: the state taken when the link was saved, else — for the article only — the
 * fingerprint of data/schedule.json (the picture the grid was typed from). null: nothing to compare with yet.
 */
export function knownFor(source: Source, typedFrom: string): string | null {
  if (source.known) return source.known;
  return source.url === DEFAULT_SOURCE.url ? typedFrom : null;
}
