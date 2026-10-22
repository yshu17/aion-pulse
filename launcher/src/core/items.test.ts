// Step 2 of the port: the item list state, recipes and tooltips match the Python golden results.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";

import { ALL_TYPES, ItemBrowser, ItemFilter } from "./items/browser";
import { parseWatchItems } from "./items/catalog";
import { parseRecipe, RecipeBook, Recipe, recipeBlock, withRecipe } from "./items/recipes";
import { parseSpecs } from "./items/specs";

const ROOT = join(__dirname, "..", "..", "..");
const golden = (name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "golden", `${name}.json`), "utf-8")).case;
const plain = (value: unknown) => JSON.parse(JSON.stringify(value));

describe("item list (ItemBrowser) on the real watch list", () => {
  const g = golden("browser");
  const items = parseWatchItems(readFileSync(join(ROOT, "data", "watch_items.csv"), "utf-8"));

  it("follows the same steps as Python", () => {
    const b = new ItemBrowser(items, [items[0].id, items[5].id, "no-such-id"], ["Лата", "Нет такой"]);
    expect([...b.groups].map(([name, group]) => [name, group.length])).toEqual(g.groups);
    expect(b.order.slice(0, 20)).toEqual(g.order_head);
    expect(b.checkedIds()).toEqual(g.checked_ids);
    expect(b.collapsed).toEqual(g.collapsed);
    expect(b.grades).toEqual(g.grades);
    expect(b.levels).toEqual(g.levels);
    expect(b.typeChoices()).toEqual(g.type_choices);

    for (const [query, want] of Object.entries(g.search as Record<string, any>)) {
      const count = b.search(query);
      expect({ count, head: b.matches.slice(0, 10), current: b.currentMatch() }, query).toEqual(want);
    }
    b.search("меч");
    expect([b.step(1), b.step(1), b.step(-1), b.step(-1), b.step(-1)]).toEqual(g.steps);

    const f1 = b.toggleGrade("epic");
    b.setFilter(f1);
    const f2 = b.toggleGrade("legend");
    b.setFilter(f2);
    expect([[...f1.grades].sort(), [...f2.grades].sort(), b.visible.length, b.grades.map((x) => b.chipState(x)),
      b.chipState("epic", false)]).toEqual(g.grade_toggles);
    b.setFilter(b.toggleGrade("epic"));
    b.setFilter(b.toggleGrade("legend"));
    expect([...b.filter.grades].sort()).toEqual(g.grades_back);

    const f3 = b.withLevelsType(55, 50, "Оружие: Меч");
    b.setFilter(f3);
    expect({ filter: [f3.level_min, f3.level_max, f3.type, f3.active], visible: b.visible.length,
      shown: [...b.shown].map(([name, group]) => [name, group.length]) }).toEqual(g.levels_type);
    b.setAll(true);
    expect({ checked: b.checked.size, group_checked: Object.fromEntries([...b.shown.keys()].map((n) => [n, b.groupChecked(n)])) })
      .toEqual(g.set_all);
    b.setFilter(new ItemFilter());
    b.setGroup("Оружие", false);
    b.toggleItem(items[1].id);
    expect({ checked: b.checked.size, has_item1: b.checked.has(items[1].id) }).toEqual(g.after_group);
    const first = b.order[0];
    b.toggleCollapsed(b.group_of.get(first)!);
    expect([b.expandFor(first), b.expandFor(first), [...b.collapsed]]).toEqual(g.expand);
    expect([b.withLevelsType(0, 0, ALL_TYPES).type, new ItemFilter().active]).toEqual(g.all_types);
  });
});

describe("recipes", () => {
  const g = golden("recipes");
  const show = (recipes: Recipe[]) => recipes.map((r) => [r.product, r.skill, r.level, r.count, r.ingredients, r.product_id]);

  it("parse odd records the way Python does", () => {
    const parsed = (g.raw as unknown[]).map(parseRecipe);
    expect(parsed.map((r) => (r === null ? null : show([r])[0]))).toEqual(g.parsed);
    const book = new RecipeBook(parsed.filter(Boolean) as Recipe[]);
    expect(book.size).toBe(g.count);
    expect(show(book.forItem("что угодно", "100000123"))).toEqual(g.by_id);
    expect(show(book.forItem("МЕЧ НАЕМНИКА"))).toEqual(g.by_name);
    expect(show(book.forItem("нет такого", "1"))).toEqual(g.missing);
    expect(plain(recipeBlock(book.forItem("Зелье")))).toEqual(g.block);
    expect(recipeBlock([])).toEqual(g.no_block);
    const spec = { name: "Меч наемника", grade: "rare", blocks: [{ kind: "text", text: "x" }] };
    expect(plain(withRecipe(spec, book.forItem("Зелье")))).toEqual(g.with_recipe);
    expect(withRecipe(spec, [])).toEqual(g.without);
  });
});

describe("tooltips (item_specs.json.gz)", () => {
  const g = golden("specs");
  it("same specs as Python", () => {
    const specs = parseSpecs(gunzipSync(readFileSync(join(ROOT, "data", "item_specs.json.gz"))).toString("utf-8"));
    expect(specs.size).toBe(g.count);
    const ids = specs.ids().sort();
    const sample = [ids[0], ids[Math.floor(ids.length / 2)], ids[ids.length - 1]];
    expect(Object.fromEntries(sample.map((id) => [id, specs.get(id)]))).toEqual(g.sample);
    expect(specs.has("no-such-id")).toBe(g.has_missing);
  });
});
