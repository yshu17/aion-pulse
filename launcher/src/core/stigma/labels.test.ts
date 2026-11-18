import { describe, expect, it } from "vitest";

import { castText, cooldownText, infoText, kindText, targetText } from "./labels";

describe("the calculator's English words in Russian", () => {
  it("names the skill's kind and target as the game does", () => {
    expect(kindText("Chain Skills")).toBe("Цепочка");
    expect(targetText("Area within a Radius of Target")).toBe("Область вокруг цели");
    expect(targetText("Something new")).toBe("Something new");
  });

  it("rewrites the extra lines with their numbers", () => {
    expect(infoText("Max targets = 6")).toBe("Целей: до 6");
    expect(infoText("Damage in PVP = 80%")).toBe("Урон в PvP: 80%");
    expect(infoText("Duration in PVP = 25%")).toBe("Длительность в PvP: 25%");
    expect(infoText("Accuracy = +500")).toBe("Точность +500");
    expect(infoText("Can jumpshot")).toBe("Можно в прыжке");
  });

  it("writes cast and cooldown times in seconds and minutes", () => {
    expect(castText("Cast Instantly")).toBe("мгновенно");
    expect(castText("0.5 sec")).toBe("0,5 с");
    expect(cooldownText("120")).toBe("2 мин");
    expect(cooldownText("90")).toBe("1 мин 30 с");
    expect(cooldownText("16")).toBe("16 с");
    expect(cooldownText("")).toBe("");
  });
});
