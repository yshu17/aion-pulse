/**
 * Craft recipes for item tooltips: «what is this made from» — the port of core/items/recipes.py.
 * Pure: `parseRecipes` takes the JSON text (the caller un-gzips data/recipes.json.gz); null or broken gives an empty book.
 */

import { casefold, pyInt, pyOr, pyStr } from "../py";

export interface Recipe {
  product: string;
  skill: string;
  level: number;
  count: number;
  ingredients: [string, number][];
  product_id: string;
}

export class RecipeBook {
  private byId = new Map<string, Recipe[]>();
  private byName = new Map<string, Recipe[]>();

  constructor(recipes: Recipe[] = []) {
    for (const recipe of recipes) {
      if (recipe.product_id) {
        if (!this.byId.has(recipe.product_id)) this.byId.set(recipe.product_id, []);
        this.byId.get(recipe.product_id)!.push(recipe);
      }
      const key = casefold(recipe.product);
      if (!this.byName.has(key)) this.byName.set(key, []);
      this.byName.get(key)!.push(recipe);
    }
  }

  get size(): number {
    let total = 0;
    for (const list of this.byName.values()) total += list.length;
    return total;
  }

  /** Recipes that make this item: by id first, then by name. */
  forItem(name: string, itemId = ""): Recipe[] {
    const byId = this.byId.get(String(itemId));
    return [...(byId && byId.length ? byId : this.byName.get(casefold(name)) ?? [])];
  }
}

/** One raw record -> Recipe, or null (no product, no usable ingredient). Odd numbers fall back as Python does. */
export function parseRecipe(raw: unknown): Recipe | null {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) return null;
  const r = raw as Record<string, unknown>;
  if (!pyStr(pyOr(r.product, "")).trim()) return null;
  const ingredients: [string, number][] = [];
  for (const entry of (pyOr(r.ingredients, []) as unknown[])) {
    if (!Array.isArray(entry) || !entry.length || !pyStr(entry[0]).trim()) continue;
    let quantity: number;
    try {
      quantity = entry.length > 1 ? pyInt(entry[1]) : 1;
    } catch {
      quantity = 1;
    }
    ingredients.push([pyStr(entry[0]).trim(), Math.max(1, quantity)]);
  }
  if (!ingredients.length) return null;
  let level: number;
  let count: number;
  try {
    level = pyInt(pyOr(r.level, 0));
    count = pyInt(pyOr(r.count, 1));
  } catch {
    level = 0;
    count = 1;
  }
  return {
    product: pyStr(r.product).trim(), skill: pyStr(pyOr(r.skill, "")).trim(), level, count: Math.max(1, count),
    ingredients, product_id: pyStr(pyOr(r.product_id, "")),
  };
}

/** data/recipes.json(.gz) text -> RecipeBook. */
export function parseRecipes(text: string | null): RecipeBook {
  let data: unknown;
  try {
    data = text === null ? null : JSON.parse(text);
  } catch {
    return new RecipeBook();
  }
  const items = data && typeof data === "object" && !Array.isArray(data) ? (data as any).recipes : null;
  return new RecipeBook(((pyOr(items, []) as unknown[]).map(parseRecipe).filter(Boolean)) as Recipe[]);
}

/** One tooltip block for all recipes of an item (some items have several ways to make them). */
export function recipeBlock(recipes: Recipe[]): Record<string, unknown> | null {
  if (!recipes.length) return null;
  return {
    kind: "recipe",
    recipes: recipes.map((r) => ({ skill: r.skill, level: r.level, count: r.count, ingredients: r.ingredients.map((i) => [...i]) })),
  };
}

/** The item spec plus the recipe block (the spec is not changed). */
export function withRecipe(spec: Record<string, any>, recipes: Recipe[]): Record<string, any> {
  const block = recipeBlock(recipes);
  if (block === null) return spec;
  return { ...spec, blocks: [...(spec.blocks ?? []), { kind: "hr" }, block] };
}
