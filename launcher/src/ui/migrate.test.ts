import { describe, expect, it } from "vitest";

import { pulseSettings } from "./migrate";

describe("settings of an old Pulse", () => {
  it("takes the first Pulse config.json and skips missing, broken and foreign ones", () => {
    const pulse = JSON.stringify({ game_dir: "D:\\Aion", keywords: ["wts"], watch_items: ["110600968"], cooldown_sec: "x" });
    const found = pulseSettings([
      ["C:\\a\\config.json", null],
      ["C:\\b\\config.json", "{broken"],
      ["C:\\c\\config.json", JSON.stringify({ theme: "dark", game_dir: "x" })], // one Pulse key only: another program
      ["C:\\d\\config.json", "[]"],
      ["C:\\e\\config.json", pulse],
      ["C:\\f\\config.json", JSON.stringify({ game_dir: "later", keywords: [] })],
    ]);
    expect(found?.from).toBe("C:\\e\\config.json");
    expect(found?.config.game_dir).toBe("D:\\Aion");
    expect(found?.config.keywords).toEqual(["wts"]);
    expect(found?.config.watch_items).toEqual(["110600968"]);
    expect(found?.config.cooldown_sec).toBe(60); // a wrong value falls back to the default, as in Pulse
    expect(found?.notice).toContain("cooldown_sec");
    expect(pulseSettings([])).toBeNull();
  });
});
