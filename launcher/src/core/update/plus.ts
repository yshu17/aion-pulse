/**
 * The update of Pulse+ from its GitHub releases: what to offer the user from the latest release.
 *
 *   offer(releaseJson, current, seen, installable) -> Offer | null
 *     null: the release is not newer than `current` or the user put this version off (`seen` is its tag);
 *     asset: the Pulse+.exe to download (url, size, SHA-256 of the notes) when this copy can install it,
 *            null when only the release page can be offered (the developer's build, no file, no checksum).
 *
 * The download, the check of the checksum and the swap of the program are the Rust side's (update_install).
 */

import { checkSource, pickAsset, type ReleaseAsset } from "./selfupdate";
import { latestRelease, newer } from "./updater";

export const REPO = "yshu17/aion-pulse";
export const PLUS_ASSET = "Pulse+.exe";

export interface Offer { tag: string; page: string; asset: ReleaseAsset | null }

export function offer(releaseJson: string, current: string, seen: string, installable: boolean): Offer | null {
  const found = latestRelease(releaseJson);
  if (found === null || !newer(found[0], current) || found[0] === seen) return null;
  let asset = installable ? pickAsset(releaseJson, PLUS_ASSET) : null;
  if (asset) {
    try { checkSource(asset); } catch { asset = null; }
  }
  return { tag: found[0], page: found[1], asset };
}
