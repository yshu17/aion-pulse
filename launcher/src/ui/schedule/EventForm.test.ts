import { describe, expect, it } from "vitest";

import { problems } from "./EventForm";
import type { Draft } from "./useSchedule";

const draft = (patch: Partial<Draft>): Draft => ({ name: "Рейд", start: "18:00", end: "19:30", days: ["thu"], chip: "Своё", bell: true, ...patch });

describe("event form checks", () => {
  it("accepts a normal event and one that ends at midnight", () => {
    expect(problems(draft({}))).toEqual({});
    expect(problems(draft({ start: "22:00", end: "24:00" }))).toEqual({});
    expect(problems(draft({ start: "22:00", end: "00:00" }))).toEqual({});
  });

  it("names each wrong field", () => {
    expect(Object.keys(problems(draft({ name: "  ", start: "25:00", days: [] })))).toEqual(["name", "time", "days"]);
    expect(problems(draft({ start: "19:00", end: "18:00" })).time).toContain("позже начала");
  });
});
