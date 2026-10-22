/**
 * Has the schedule on the knowledge base changed? — the port of core/schedule/schedule_update.py.
 *
 * The grid picture's name plus its ETag and Last-Modified form a fingerprint; data/schedule.json keeps the
 * fingerprint of the grid it was typed from (image, image_etag, image_modified).
 *   siteFingerprint(fetch)                 fetch(url, method) -> [text, headers]; throws on a page without the picture
 *   decide(known, current, seen, manual)   "changed", "same" or null (say nothing)
 */

export const ARTICLE = "https://kb.aionempire.com/article/rasapisanie";
const PICTURE = /https:\/\/[^"'\s<>]*\/schedule[^"'\s<>/]*\.(?:jpg|jpeg|png|webp)/i;

export type Fetch = (url: string, method: "GET" | "HEAD") => Promise<[string, Record<string, string>]>;

export function imageUrl(html: string): string | null {
  const match = PICTURE.exec(html);
  return match ? match[0] : null;
}

export function fingerprint(name: string, etag: string, modified: string): string {
  return `${name.slice(name.lastIndexOf("/") + 1)}|${etag}|${modified}`;
}

export function knownFingerprint(data: Record<string, unknown>): string {
  const get = (key: string) => (typeof data[key] === "string" ? (data[key] as string) : "");
  return fingerprint(get("image"), get("image_etag"), get("image_modified"));
}

export async function siteFingerprint(fetch: Fetch): Promise<string> {
  const [page] = await fetch(ARTICLE, "GET");
  const url = imageUrl(page);
  if (url === null) throw new Error("на странице нет картинки расписания");
  const [, headers] = await fetch(url, "HEAD");
  return fingerprint(url, headers["ETag"] ?? "", headers["Last-Modified"] ?? "");
}

/** At start only a new, not yet acknowledged version is reported; a manual check always answers. */
export function decide(known: string, current: string, seen: string, manual: boolean): "changed" | "same" | null {
  if (current === known) return manual ? "same" : null;
  if (current === seen && !manual) return null;
  return "changed";
}
