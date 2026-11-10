import { describe, expect, it } from "vitest";

import { bonusLine, cleanSkillText } from "./statNames";

describe("the client's stat keys", () => {
  it("name a stat in any case and sign its value; percents where the game shows them", () => {
    expect(bonusLine("maxHp 20")).toEqual(["Макс. HP", "+20"]);
    expect(bonusLine("MaxHP 20")).toEqual(["Макс. HP", "+20"]);
    expect(bonusLine("speed 10")).toEqual(["Скорость движения", "+10%"]);
    expect(bonusLine("PVPAttackRatio 52")).toEqual(["Урон в ПвП", "+5.2%"]); // tenths of a percent
    expect(bonusLine("AttackDelay -5")).toEqual(["Задержка атаки", "-5%"]);
    expect(bonusLine("Unknown 3")).toEqual(["Unknown", "3"]);
  });

  it("take the client's placeholders out of a skill's text", () => {
    expect(cleanSkillText("наносит цели [%e1.SkillATK_Instant.MinDamage]-[%e1.SkillATK_Instant.MaxDamage] ед. урона"))
      .toBe("наносит цели … ед. урона");
  });
});
