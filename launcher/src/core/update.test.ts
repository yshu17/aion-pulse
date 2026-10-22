// Step 9 of the port: the self-update checks replay the Python golden results (tools/golden_update.py).
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { ASSET, canInstall, download, HOSTS, OLD_SUFFIX, pickAsset, UpdateError } from "./update/selfupdate";

const ROOT = join(__dirname, "..", "..", "..");
const golden = (name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "golden", `${name}.json`), "utf-8")).case;

/** golden_update.PAYLOAD: bytes 0..255 seven hundred times, then «Pulse». */
const PAYLOAD = new Uint8Array([...Array(700)].flatMap(() => [...Array(256).keys()]).concat([...Buffer.from("Pulse")]));

async function* chunks(data: Uint8Array, size = 64 * 1024) {
  for (let i = 0; i < data.length; i += size) yield data.subarray(i, i + size);
}

const sha256 = () => {
  const hash = createHash("sha256");
  return { update: (c: Uint8Array) => { hash.update(c); }, hex: () => hash.digest("hex") };
};

describe("self-update", () => {
  const g = golden("update_self");
  it("picks the asset and checks address, size and checksum as in Python", async () => {
    expect([ASSET, HOSTS, OLD_SUFFIX]).toEqual(g.consts);
    expect([createHash("sha256").update(PAYLOAD).digest("hex"), PAYLOAD.length]).toEqual([g.payload.sha256, g.payload.size]);
    for (const [body, want] of g.pick) expect(pickAsset(body), body).toEqual(want);
    for (const [index, [asset, length, want, progressWant, leftWant]] of g.download.entries()) {
      const progress: number[][] = [];
      let written = 0;
      let state = "none"; // none -> part -> kept | dropped
      const sink = {
        write: (c: Uint8Array) => { state = "part"; written += c.length; },
        commit: () => { state = "kept"; },
        discard: () => { state = "dropped"; },
      };
      const headers = length === null ? {} : { "Content-Length": length };
      let result: unknown;
      try {
        await download(asset, async () => ({ headers, chunks: chunks(PAYLOAD) }), sink, sha256, (d, t) => progress.push([d, t]));
        result = { ok: written === PAYLOAD.length };
      } catch (error) {
        if (!(error instanceof UpdateError)) throw error;
        result = { error: error.message };
      }
      const name = `Pulse${Math.floor(index / 2)}.exe`;
      const left = state === "kept" ? [name] : state === "part" ? [`${name}.part`] : []; // a dropped part is gone
      expect([result, progress, left], `${asset.url} ${length}`).toEqual([want, progressWant, leftWant]);
    }
    expect([canInstall(true, "Pulse.exe"), canInstall(true, "PULSE.EXE"), canInstall(false, "Pulse.exe"),
      canInstall(true, "Pulse-test.exe")]).toEqual([true, true, false, false]);
  });
});
