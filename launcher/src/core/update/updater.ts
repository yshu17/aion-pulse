/** Update check against the latest GitHub release — the port of core/update/updater.py. */

export function releaseApi(repo: string): string {
  return `https://api.github.com/repos/${repo}/releases/latest`;
}

/** «v1.2.10» -> [1, 2, 10]; unreadable parts count as 0. */
export function parseVersion(text: string): number[] {
  return text.trim().replace(/^[vV]+/, "").split(".").map((part) => (/^\d+$/.test(part) ? parseInt(part, 10) : 0));
}

/** [tag, page url] of a GitHub release JSON, or null when the answer has no tag. */
export function latestRelease(body: string): [string, string] | null {
  const data = JSON.parse(body);
  const tag = data.tag_name ?? "";
  const url = data.html_url ?? "";
  return tag && url ? [tag, url] : null;
}

/** Python tuple comparison: element by element, a shorter equal prefix is smaller. */
export function newer(latest: string, current: string): boolean {
  const a = parseVersion(latest);
  const b = parseVersion(current);
  for (let i = 0; i < Math.min(a.length, b.length); i++) if (a[i] !== b[i]) return a[i] > b[i];
  return a.length > b.length;
}
