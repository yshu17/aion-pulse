import { describe, expect, it } from "vitest";

import { ARTICLE, Fetch, isImageUrl, sourceFingerprint } from "../../core/schedule/scheduleUpdate";
import { DEFAULT_SOURCE, knownFor, parseSource, serializeSource, webAddress } from "./source";

describe("schedule source link", () => {
  it("takes only https addresses of a public name", () => {
    expect(webAddress("  https://kb.aionempire.com/article/rasapisanie ")).toBe("https://kb.aionempire.com/article/rasapisanie");
    expect(webAddress("http://example.com/schedule.jpg")).toBeNull();
    expect(webAddress("javascript:alert(1)")).toBeNull();
    expect(webAddress("file:///C:/Windows/system.ini")).toBeNull();
    expect(webAddress("https://intranet/")).toBeNull();
    expect(webAddress("https://127.0.0.1/x.jpg")).toBeNull(); // this computer
    expect(webAddress("https://192.168.0.1:8080/")).toBeNull(); // the local network
    expect(webAddress("https://[::1]/")).toBeNull();
    expect(webAddress("https://printer.local/")).toBeNull();
    expect(webAddress("https://aionempire.com@evil.net/")).toBeNull(); // a login hides the real host
    expect(webAddress("https://example.org:8443/a.png")).toBe("https://example.org:8443/a.png");
    expect(webAddress("не адрес")).toBeNull();
    expect(webAddress("")).toBeNull();
  });

  it("reads the saved source and falls back to the article when the file is missing or broken", () => {
    expect(parseSource(null)).toEqual(DEFAULT_SOURCE);
    expect(parseSource("не json")).toEqual(DEFAULT_SOURCE);
    expect(parseSource('{"url":"http://plain.example.com/x.jpg"}')).toEqual(DEFAULT_SOURCE);
    expect(parseSource('{"url":"https://example.com/s.jpg","known":"s.jpg|e|m"}')).toEqual({ url: "https://example.com/s.jpg", known: "s.jpg|e|m" });
    expect(parseSource('{"url":"https://example.com/s.jpg","known":5}')).toEqual({ url: "https://example.com/s.jpg", known: null });
    const saved = { url: "https://example.com/s.jpg", known: "s.jpg|e|m" };
    expect(parseSource(serializeSource(saved))).toEqual(saved);
  });

  it("compares a custom link only with the state taken when it was saved; the article also with the typed grid", () => {
    expect(knownFor({ url: ARTICLE, known: null }, "typed")).toBe("typed");
    expect(knownFor({ url: ARTICLE, known: "taken" }, "typed")).toBe("taken"); // «Сохранить» took the current state
    expect(knownFor({ url: "https://example.com/s.jpg", known: null }, "typed")).toBeNull(); // nothing to compare with yet
    expect(knownFor({ url: "https://example.com/s.jpg", known: "taken" }, "typed")).toBe("taken");
  });
});

describe("fingerprint of a schedule link", () => {
  const PAGE = '<img src="https://news.example.com/media/schedule-21ru.jpg">';
  const headers = { ETag: '"abc"', "Last-Modified": "Mon, 26 Oct 2026 10:00:00 GMT" };

  it("knows a picture address from a page address", () => {
    expect(isImageUrl("https://example.com/a/schedule.JPG")).toBe(true);
    expect(isImageUrl("https://example.com/a/schedule.png?v=2")).toBe(true);
    expect(isImageUrl("https://kb.aionempire.com/article/rasapisanie")).toBe(false);
  });

  it("asks the headers of a picture once, and the page and then the picture for a page", async () => {
    const asked: string[] = [];
    const fetch: Fetch = async (url, method) => { asked.push(`${method} ${url}`); return [method === "GET" ? PAGE : "", headers]; };
    expect(await sourceFingerprint(fetch, "https://example.com/m/schedule-20ru.jpg")).toBe('schedule-20ru.jpg|"abc"|Mon, 26 Oct 2026 10:00:00 GMT');
    expect(asked).toEqual(["HEAD https://example.com/m/schedule-20ru.jpg"]);
    asked.length = 0;
    expect(await sourceFingerprint(fetch, "https://example.com/page")).toBe('schedule-21ru.jpg|"abc"|Mon, 26 Oct 2026 10:00:00 GMT');
    expect(asked).toEqual(["GET https://example.com/page", "HEAD https://news.example.com/media/schedule-21ru.jpg"]);
  });

  it("says so when a page has no schedule picture", async () => {
    const fetch: Fetch = async () => ["<p>нет</p>", {}];
    await expect(sourceFingerprint(fetch, "https://example.com/page")).rejects.toThrow("нет картинки расписания");
  });
});
