import { describe, expect, it } from "vitest";

import { ARTICLE } from "../../core/schedule/scheduleUpdate";
import { linkName, parseLinks, webAddress } from "./links";

describe("schedule links", () => {
  it("opens only web addresses", () => {
    expect(webAddress(" https://kb.aionempire.com/article/rasapisanie ")).toBe("https://kb.aionempire.com/article/rasapisanie");
    expect(webAddress("http://example.com")).toBe("http://example.com/");
    expect(webAddress("javascript:alert(1)")).toBeNull();
    expect(webAddress("file:///C:/Windows/system.ini")).toBeNull();
    expect(webAddress("не адрес")).toBeNull();
    expect(webAddress("")).toBeNull();
  });

  it("reads the user's links and drops broken entries", () => {
    const text = JSON.stringify([
      { name: "Гайд", url: "https://example.com/guide" },
      { name: "", url: "https://example.com/empty-name" },
      { name: "Плохая", url: "javascript:alert(1)" },
      { name: 5, url: "https://example.com" },
    ]);
    expect(parseLinks(text)).toEqual([{ name: "Гайд", url: "https://example.com/guide" }]);
    expect(parseLinks("не json")).toEqual([]);
    expect(parseLinks(null)).toEqual([]);
    expect(parseLinks('{"a":1}')).toEqual([]);
  });

  it("names a new link by what was typed, else by the host, and keeps the name short", () => {
    expect(linkName("  Мой гайд ", "https://example.com/x")).toBe("Мой гайд");
    expect(linkName("", "https://example.com/x")).toBe("example.com");
    expect(linkName("а".repeat(100), "https://example.com")).toHaveLength(60);
  });

  it("keeps the built-in article as an address the program knows", () => {
    expect(webAddress(ARTICLE)).toBe(ARTICLE);
  });
});
