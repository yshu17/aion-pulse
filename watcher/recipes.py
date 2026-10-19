"""Craft recipes for item tooltips: «what is this made from». Tk-free.

Data file `data/recipes.json.gz` (or .json), built from the game client's combine-recipe table:

    {"schema": 1,
     "recipes": [{"product": "Меч наемника",              # item name of the result
                  "product_id": "100000123",              # optional: item id
                  "count": 1,                             # items made, default 1
                  "skill": "Оружейное дело", "level": 300,
                  "ingredients": [["Железо", 5], ["Кожа", 2]]}]}

Public API:
    load_recipes(path) -> RecipeBook                      missing or broken file gives an empty book
    RecipeBook.for_item(name, item_id="") -> [Recipe]     recipes that make this item (by id first, then by name)
    recipe_block(recipes) -> dict | None                  a tooltip block {"kind": "recipe", ...}, None when no recipe
    with_recipe(spec, recipes) -> dict                    the item spec plus the recipe block (the spec is not changed)
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Recipe:
    product: str
    skill: str = ""
    level: int = 0
    count: int = 1
    ingredients: tuple[tuple[str, int], ...] = field(default_factory=tuple)
    product_id: str = ""


class RecipeBook:
    def __init__(self, recipes: list[Recipe] | None = None) -> None:
        self._by_id: dict[str, list[Recipe]] = {}
        self._by_name: dict[str, list[Recipe]] = {}
        for recipe in recipes or []:
            if recipe.product_id:
                self._by_id.setdefault(recipe.product_id, []).append(recipe)
            self._by_name.setdefault(recipe.product.casefold(), []).append(recipe)

    def __len__(self) -> int:
        return sum(len(v) for v in self._by_name.values())

    def for_item(self, name: str, item_id: str = "") -> list[Recipe]:
        return list(self._by_id.get(str(item_id)) or self._by_name.get(name.casefold(), []))


def _recipe(raw: object) -> Recipe | None:
    if not isinstance(raw, dict) or not str(raw.get("product") or "").strip():
        return None
    ingredients = []
    for entry in raw.get("ingredients") or []:
        if isinstance(entry, (list, tuple)) and entry and str(entry[0]).strip():
            try:
                quantity = int(entry[1]) if len(entry) > 1 else 1
            except (TypeError, ValueError):
                quantity = 1
            ingredients.append((str(entry[0]).strip(), max(1, quantity)))
    if not ingredients:
        return None
    try:
        level, count = int(raw.get("level") or 0), int(raw.get("count") or 1)
    except (TypeError, ValueError):
        level, count = 0, 1
    return Recipe(str(raw["product"]).strip(), str(raw.get("skill") or "").strip(), level, max(1, count),
                  tuple(ingredients), str(raw.get("product_id") or ""))


def load_recipes(path: Path) -> RecipeBook:
    try:
        raw = Path(path).read_bytes()
        if Path(path).suffix == ".gz":
            raw = gzip.decompress(raw)
        data = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError, EOFError):
        return RecipeBook()
    items = data.get("recipes") if isinstance(data, dict) else None
    return RecipeBook([r for r in map(_recipe, items or []) if r is not None])


def recipe_block(recipes: list[Recipe]) -> dict | None:
    """One tooltip block for all recipes of an item (some items have several ways to make them)."""
    if not recipes:
        return None
    return {"kind": "recipe", "recipes": [
        {"skill": r.skill, "level": r.level, "count": r.count, "ingredients": [list(i) for i in r.ingredients]}
        for r in recipes
    ]}


def with_recipe(spec: dict, recipes: list[Recipe]) -> dict:
    block = recipe_block(recipes)
    if block is None:
        return spec
    return {**spec, "blocks": [*spec.get("blocks", []), {"kind": "hr"}, block]}
