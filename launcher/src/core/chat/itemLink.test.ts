import { describe, expect, it } from "vitest";

import { cleanText, itemLink } from "./parser";

describe("item link copied for the game's chat", () => {
  it("is the game's own item link: the chat shows the item's name", () => {
    expect(itemLink("166000103")).toBe("[item:166000103]");
    expect(cleanText(itemLink("166000103"), { "166000103": "Меч Фланаса" })).toContain("Меч Фланаса");
  });
});
