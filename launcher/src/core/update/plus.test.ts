import { describe, expect, it } from "vitest";

import { PLUS_ASSET, offer } from "./plus";

const SHA = "4465cfacab20fb494e335fd69c42e05f0841682de53e2b0d9a0a8ab939c7555c";
const release = (tag: string, assets: string[], body = `Новое\n\nSHA256: ${SHA}\n`) => JSON.stringify({
  tag_name: tag, html_url: `https://github.com/yshu17/aion-pulse/releases/tag/${tag}`, body,
  assets: assets.map((name) => ({ name, size: 100, browser_download_url: `https://github.com/yshu17/aion-pulse/releases/download/${tag}/${name}` })),
});

describe("the Pulse+ update offer", () => {
  it("offers a newer release with its Pulse+.exe, size and checksum when this copy can install", () => {
    expect(PLUS_ASSET).toBe("Pulse+.exe");
    expect(offer(release("v2.1.0", ["Pulse+.exe"]), "2.0.0", "", true)).toEqual({
      tag: "v2.1.0", page: "https://github.com/yshu17/aion-pulse/releases/tag/v2.1.0",
      asset: { url: "https://github.com/yshu17/aion-pulse/releases/download/v2.1.0/Pulse+.exe", size: 100, sha256: SHA },
    });
  });

  it("offers nothing for the same or an older version, or a version the user put off", () => {
    expect(offer(release("v2.0.0", ["Pulse+.exe"]), "2.0.0", "", true)).toBeNull();
    expect(offer(release("v1.2.0", ["Pulse.exe"]), "2.0.0", "", true)).toBeNull();
    expect(offer(release("v2.1.0", ["Pulse+.exe"]), "2.0.0", "v2.1.0", true)).toBeNull();
  });

  it("offers only the release page when this copy cannot install, the file is missing or the notes have no checksum", () => {
    expect(offer(release("v2.1.0", ["Pulse+.exe"]), "2.0.0", "", false)!.asset).toBeNull(); // the developer's build
    expect(offer(release("v2.1.0", ["Pulse.exe"]), "2.0.0", "", true)!.asset).toBeNull(); // the old program's file
    expect(offer(release("v2.1.0", ["Pulse+.exe"], "без суммы"), "2.0.0", "", true)!.asset).toBeNull();
  });
});
