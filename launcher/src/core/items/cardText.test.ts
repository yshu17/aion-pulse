import { describe, expect, it } from "vitest";

import { cleanCard, cleanCardText } from "./cardText";

describe("the broken texts of the item cards", () => {
  it("drops the «%» the site left before the plus: the number is a flat one", () => {
    expect(cleanCardText("Уклонение% +5. Маг. защита% +10. Время действия: 30 мин.")).toBe("Уклонение +5. Маг. защита +10. Время действия: 30 мин.");
    expect(cleanCardText("Физ. крит% +10. Макс. HP% +40.")).toBe("Физ. крит +10. Макс. HP +40.");
  });

  it("keeps a real percent, which stands after the number", () => {
    expect(cleanCardText("Скорость атаки +9%. Макс. HP +40%.")).toBe("Скорость атаки +9%. Макс. HP +40%.");
  });

  it("names the client's raw key", () => {
    expect(cleanCardText("ElementalDefendAll% +10. Время действия: 30 мин.")).toBe("Защ. от стихий +10. Время действия: 30 мин.");
  });

  it("says that a bonus has no number instead of printing a bare plus", () => {
    expect(cleanCardText("Макс. HP +40. Время полета% +. Время действия: 30 мин."))
      .toBe("Макс. HP +40. Время полета: значение в клиенте не указано. Время действия: 30 мин.");
    expect(cleanCardText("Время полета +")).toBe("Время полета: значение в клиенте не указано.");
  });

  it("cleans only the text blocks of a card and leaves the rest as it is", () => {
    const card = { name: "Суп", blocks: [{ kind: "hr" }, { kind: "text", text: "Точность% +10." }, { kind: "props", lines: ["[Нельзя обменять]"] }] };
    expect(cleanCard(card)).toEqual({ name: "Суп", blocks: [{ kind: "hr" }, { kind: "text", text: "Точность +10." }, { kind: "props", lines: ["[Нельзя обменять]"] }] });
    expect(cleanCard(null)).toBeNull();
  });
});
