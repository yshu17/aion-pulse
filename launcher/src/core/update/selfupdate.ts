/**
 * Install a newer Pulse.exe from its GitHub release — the port of the checks in core/update/selfupdate.py.
 *
 * Steps: pick the Pulse.exe asset of the release, download it over HTTPS, check its size and its SHA-256 against the
 * value in the release notes (a line «SHA256: <64 hex>»). Nothing is installed without a checksum: a release without
 * «SHA256:» in its notes is offered as a page, not an install.
 *
 * Network, file and hash come in as parameters (`open`, `sink`, `sha256`); swapping the running exe (Python's install
 * and remove_old) is the program shell's job — in the launcher, Tauri's updater.
 */

import { pyInt } from "../py";

export const ASSET = "Pulse.exe";
export const HOSTS = ["github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"];
export const OLD_SUFFIX = ".old";
const SHA_LINE = /SHA256\s*[:=]\s*([0-9a-fA-F]{64})/;

export interface ReleaseAsset {
  url: string;
  size: number;
  sha256: string;
}

export class UpdateError extends Error {}

const truthy = (v: unknown) => !(v === null || v === undefined || v === false || v === 0 || v === "" || (Array.isArray(v) && !v.length));

/** The Pulse.exe of a release: {url, size, sha256}; null when there is no such asset. */
export function pickAsset(releaseJson: string): ReleaseAsset | null {
  const data = JSON.parse(releaseJson);
  for (const asset of (truthy(data.assets) ? data.assets : []) as Record<string, unknown>[]) {
    if (asset.name === ASSET && truthy(asset.browser_download_url)) {
      const found = SHA_LINE.exec(truthy(data.body) ? String(data.body) : "");
      return { url: String(asset.browser_download_url), size: truthy(asset.size) ? pyInt(asset.size) : 0,
        sha256: found ? found[1].toLowerCase() : "" };
    }
  }
  return null;
}

/** Only the stable exe of a built program: never the source tree or the local test build. */
export function canInstall(frozen: boolean, exeName: string): boolean {
  return frozen && exeName.toLowerCase() === ASSET.toLowerCase();
}

/** Python urlparse(url).hostname: the host after any «user@», without the port, lower case; null when empty. */
function hostname(url: string): [string, string | null] {
  const match = /^([A-Za-z][A-Za-z0-9+.-]*):(.*)$/.exec(url);
  if (!match) return ["", null];
  const scheme = match[1].toLowerCase();
  if (!match[2].startsWith("//")) return [scheme, null];
  const netloc = match[2].slice(2).split(/[/?#]/)[0];
  let host = netloc.slice(netloc.lastIndexOf("@") + 1);
  host = host.startsWith("[") ? host.slice(1, host.indexOf("]") >>> 0) : host.split(":")[0];
  return [scheme, host ? host.toLowerCase() : null];
}

/** Throws UpdateError when the asset must not be fetched: no checksum, not HTTPS or not a GitHub host. */
export function checkSource(asset: ReleaseAsset): void {
  if (!asset.sha256) throw new UpdateError("no SHA256 in the release notes");
  const [scheme, host] = hostname(asset.url);
  if (scheme !== "https" || host === null || !HOSTS.includes(host)) throw new UpdateError("update from an untrusted address");
}

export interface Answer {
  headers: Record<string, string | undefined>;
  chunks: AsyncIterable<Uint8Array>;
}

/** Where the download goes: written to a temporary part, kept by commit(), dropped by discard(). */
export interface Sink {
  write(chunk: Uint8Array): void | Promise<void>;
  commit(): void | Promise<void>;
  discard(): void | Promise<void>;
}

export interface Hasher {
  update(chunk: Uint8Array): void;
  hex(): string;
}

/** Fetch the asset into the sink. Throws UpdateError (untrusted address, no checksum, wrong size or hash). */
export async function download(asset: ReleaseAsset, open: (url: string) => Promise<Answer>, sink: Sink,
                               sha256: () => Hasher, progress: (done: number, total: number) => void = () => {}): Promise<void> {
  checkSource(asset);
  const answer = await open(asset.url);
  const digest = sha256();
  const length = answer.headers["Content-Length"];
  const total = truthy(length) ? pyInt(length) : truthy(asset.size) ? asset.size : 0;
  let done = 0;
  for await (const chunk of answer.chunks) {
    if (!chunk.length) break;
    await sink.write(chunk);
    digest.update(chunk);
    done += chunk.length;
    progress(done, total);
  }
  if (asset.size && done !== asset.size) {
    await sink.discard();
    throw new UpdateError("download is incomplete");
  }
  if (digest.hex() !== asset.sha256) {
    await sink.discard();
    throw new UpdateError("SHA-256 does not match the release notes");
  }
  await sink.commit();
}
