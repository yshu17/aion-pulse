import gzip
import json

from watcher.recipes import RecipeBook, load_recipes, recipe_block, with_recipe


def _write(path, recipes):
    path.write_bytes(gzip.compress(json.dumps({"schema": 1, "recipes": recipes}).encode("utf-8")))


def test_recipe_is_found_by_id_then_by_name_ignoring_case(tmp_path):
    path = tmp_path / "recipes.json.gz"
    _write(path, [
        {"product": "Меч наемника", "product_id": "100", "skill": "Оружейное дело", "level": 300,
         "ingredients": [["Железо", 5], ["Кожа", 2]]},
        {"product": "Щит", "ingredients": [["Железо", 3]]},
    ])
    book = load_recipes(path)
    assert len(book) == 2
    assert book.for_item("что-то другое", "100")[0].product == "Меч наемника"  # by id
    assert book.for_item("ЩИТ")[0].ingredients == (("Железо", 3),)  # by name, any case
    assert book.for_item("Нет такого") == []


def test_broken_or_missing_file_gives_an_empty_book(tmp_path):
    assert len(load_recipes(tmp_path / "missing.json.gz")) == 0
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    assert len(load_recipes(tmp_path / "bad.json")) == 0
    _write(tmp_path / "junk.json.gz", [{"product": ""}, {"product": "Меч"}, "x", {"product": "Лук", "ingredients": [["Дерево", "много"]]}])
    book = load_recipes(tmp_path / "junk.json.gz")
    assert [r.product for r in book.for_item("Лук")] == ["Лук"]  # a bad quantity becomes 1, rows without ingredients are dropped
    assert book.for_item("Меч") == []


def test_tooltip_block_is_added_to_a_copy_of_the_spec(tmp_path):
    _write(tmp_path / "r.json.gz", [{"product": "Меч", "skill": "Оружейное дело", "level": 300, "ingredients": [["Железо", 5]]}])
    book = load_recipes(tmp_path / "r.json.gz")
    spec = {"name": "Меч", "blocks": [{"kind": "text", "text": "x"}]}
    result = with_recipe(spec, book.for_item("Меч"))
    assert result["blocks"][-1]["kind"] == "recipe" and result["blocks"][-2] == {"kind": "hr"}
    assert spec["blocks"] == [{"kind": "text", "text": "x"}]  # the original spec is unchanged
    assert with_recipe(spec, []) is spec and recipe_block([]) is None
    assert RecipeBook().for_item("Меч") == []


def test_tooltip_renders_the_recipe_block():
    import tkinter as tk
    from watcher.tooltip import SpecTooltip

    root = tk.Tk()
    try:
        tip = SpecTooltip(root)
        spec = {"name": "Меч", "grade": "common", "blocks": [
            {"kind": "recipe", "recipes": [{"skill": "Оружейное дело", "level": 300, "count": 2,
                                           "ingredients": [["Железо", 5], ["Кожа", 1]]}]}]}
        tip.show(spec, None, 10, 10)
        texts = []

        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Label):
                    texts.append(child.cget("text"))
                walk(child)

        walk(tip.window)
        assert "Создаётся по рецепту: Оружейное дело, 300" in texts
        assert "•  Железо  ×5" in texts and "•  Кожа" in texts
        assert "Создаётся предметов: 2" in texts
        tip.hide()
    finally:
        root.destroy()
