import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
import { describe, expect, it } from "vitest";

import { needsOf } from "./calc";
import { classStigmas, PLACES, treeEdges, type CalcData } from "./data";
import { clientStigmas, family, mergeNeeds, mergeStigmas, readDb } from "./merge";

const ROOT = join(__dirname, "..", "..", "..", "..");
const DATA = JSON.parse(readFileSync(join(ROOT, "data", "stigma", "classic24.json"), "utf8")) as CalcData;
const CLASSES = ["fighter", "knight", "assassin", "ranger", "wizard", "elementalist", "chanter", "cleric"];

describe("a tree's arrows", () => {
  it("go to each needed stigma from its nearest place in an earlier column, as the calculator draws them", () => {
    const tree = ["divine", "break", "wrath", "brain", "sink", "break", "wrath", "wish", "wave", "shield"];
    const needs: [string, string][] = [["brain", "divine"], ["brain", "break"], ["sink", "wrath"], ["wish", "brain"], ["wish", "sink"],
      ["wave", "break"], ["wave", "wrath"], ["shield", "wish"], ["shield", "wave"]];
    expect(treeEdges(tree, needs).sort()).toEqual([[0, 3], [1, 3], [2, 4], [3, 7], [4, 7], [5, 8], [6, 8], [7, 9], [8, 9]].sort());
  });
});

describe("data/stigma/classic24.json (the calculator's data)", () => {
  it("has the eight classes of Aion 2.x", () => {
    expect(Object.keys(DATA.classes).sort()).toEqual([...CLASSES].sort());
  });

  for (const cls of CLASSES) for (const faction of ["elyos", "asmodian"] as const) {
    it(`${cls}, ${faction}: two trees of ten places, nothing needs itself`, () => {
      const { needs, trees } = classStigmas(DATA, cls, faction);
      expect(trees.map((t) => t.length)).toEqual([PLACES.length, PLACES.length]);
      for (const [s] of needs) expect(needsOf(needs, s)).not.toContain(s);
    });
  }

  it("shows a faction only its own stigmas and the shared ones", () => {
    const { stigmas } = classStigmas(DATA, "ranger", "elyos");
    expect(stigmas.some((s) => s.faction === "asmodian")).toBe(false);
    expect(stigmas.some((s) => s.faction === "elyos")).toBe(true);
  });
});

// the database this computer has: the staged one when a running Pulse+ holds the old file (docs/ADR-003-pulse-db-replace.md)
const DB = [join(ROOT, "data", "pulse.db.new"), join(ROOT, "data", "pulse.db")].find((f) => existsSync(f));
const fresh = !!DB && Number((new DatabaseSync(DB, { readOnly: true }).prepare("PRAGMA user_version").get() as { user_version: number }).user_version) >= 10;

describe.skipIf(!fresh)("the calculator's data with this computer's pulse.db", () => {
  it("gives every level a Russian name and a stone, and mends the calculator's wrong skill ids", async () => {
    const db = new DatabaseSync(DB!, { readOnly: true });
    const all = async (sql: string, params: unknown[] = []) => db.prepare(sql).all(...(params as any[])) as Record<string, any>[];
    for (const cls of CLASSES) {
      const git = DATA.classes[cls].stigmas;
      const { skills, stones } = await readDb(all, git.flatMap((s) => s.levels.map((l) => l.skill)));
      const names = new Map(skills.map((s) => [s.id, s.internal_name]));
      for (const st of stones) names.set(st.skill_id, st.internal_name);
      for (const s of mergeStigmas(git, skills, stones)) {
        const families = new Set(s.levels.map((l) => family(names.get(l.skill) ?? "")));
        expect(families.size, `${cls} ${s.id}: ${[...families]}`).toBeLessThanOrEqual(s.id === "p_equip_dual" ? 2 : 1);
        for (const l of s.levels) expect(l.name, `${s.id} ${l.level}`).toMatch(/[А-Яа-яЁё]/);
      }
    }
    for (const cls of CLASSES) for (const faction of ["elyos", "asmodian"] as const) {
      const { stigmas, trees, needs } = classStigmas(DATA, cls, faction);
      const { skills, stones } = await readDb(all, stigmas.flatMap((s) => s.levels.map((l) => l.skill)));
      const merged = mergeNeeds(stigmas, needs, skills, stones);
      for (const [s] of merged) expect(needsOf(merged, s), `${cls} ${s}`).not.toContain(s);
      for (const tree of trees) {
        const edges = treeEdges(tree, merged);
        for (const [s, n] of merged) {
          if (!tree.includes(s)) continue;
          expect(tree, `${cls} ${faction}: ${s} needs ${n}`).toContain(n);
          expect(edges.some(([a, b]) => tree[a] === n && tree[b] === s), `${cls} ${faction}: ${s} <- ${n}`).toBe(true);
        }
      }
      if (cls === "elementalist") expect(merged.filter(([s]) => s === "el_sleepingspirit").map(([, n]) => n).sort()).toEqual(["el_enchantmentburst", "el_silence"]);
    }
    const allGit = Object.values(DATA.classes).flatMap((c) => c.stigmas);
    const everything = await readDb(all, allGit.flatMap((s) => s.levels.map((l) => l.skill)));
    const assassin = clientStigmas("assassin", "elyos", allGit, everything.skills, everything.stones);
    expect(assassin.find((s) => s.id === "as_instantrecall")?.levels[0]).toMatchObject({ level: 48, shards: 144 });
    for (const cls of CLASSES) for (const s of clientStigmas(cls, "asmodian", allGit, everything.skills, everything.stones)) {
      expect(DATA.classes[cls].stigmas.some((g) => g.id === s.id), `${cls} ${s.id}`).toBe(false);
      for (const l of s.levels) expect(l.name, `${cls} ${s.id}`).toMatch(/[А-Яа-яЁё]/);
    }
    const knight = mergeStigmas(DATA.classes.knight.stigmas, ...Object.values(await readDb(all, DATA.classes.knight.stigmas.flatMap((s) => s.levels.map((l) => l.skill)))) as [never, never]);
    expect(knight.find((s) => s.id === "kn_breakpower")!.levels.find((l) => l.level === 52)!.skill).toBe(2055);
  });
});
