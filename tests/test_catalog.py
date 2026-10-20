from core.items.catalog import WatchItem, load_item_names, load_watch_items
from watcher.paths import resource_root


def test_load_item_names(tmp_path):
    path = tmp_path / "item_names.tsv"
    path.write_text("100000893\tКлинок Рудры\n100001081\tМеч Фланаса\n\nbroken line\n", encoding="utf-8")
    assert load_item_names(path) == {"100000893": "Клинок Рудры", "100001081": "Меч Фланаса"}
    assert load_item_names(tmp_path / "nope.tsv") == {}


def test_load_watch_items(tmp_path):
    path = tmp_path / "watch_items.csv"
    path.write_text("id,name,level\n100000893,Клинок Рудры,55\n100001081,Меч Фланаса,55\n", encoding="utf-8")
    assert load_watch_items(path) == [
        WatchItem(id="100000893", name="Клинок Рудры", level=55, category="Прочее"),
        WatchItem(id="100001081", name="Меч Фланаса", level=55, category="Прочее"),
    ]
    path.write_text("id,name,level,category\n1,Кираса Рудры,55,Лата\n2,Без категории,55,\n", encoding="utf-8")
    assert [i.category for i in load_watch_items(path)] == ["Лата", "Прочее"]
    assert load_watch_items(tmp_path / "nope.csv") == []


def test_bundled_data_present():
    data = resource_root() / "data"
    items = load_watch_items(data / "watch_items.csv")
    from core.items.catalog import is_listed

    assert len(items) > 25000  # equipment from level 45, plus materials, supplies and misc for chat links
    listed = [item for item in items if is_listed(item)]
    assert len(listed) > 9000 and all(item.level >= 45 for item in listed)
    assert {item.category for item in items} >= {"Украшения", "Изготовление", "Припасы", "Прочее"}
    by_id = {item.id: item for item in items}
    assert by_id["100000893"].name == "Клинок Рудры"
    assert by_id["100000893"].grade == "epic"
    names = load_item_names(data / "item_names.tsv")
    assert names["100000893"] == "Клинок Рудры"
    with_icon = [item for item in items if (data / "icons" / f"{item.icon}.png").is_file()]
    assert len(with_icon) > 0.9 * len(items)  # a few icons are missing on the site; placeholder then
    from core.items.catalog import CATEGORY_ORDER

    assert by_id["187000018"].name == "Крылья Рудры" and by_id["187000018"].category == "Крылья"
    assert by_id["110600968"].category == "Лата"
    assert all(i.category in CATEGORY_ORDER for i in items)


def test_category_for():
    from core.items.catalog import category_for

    assert category_for("Латная броня", "Кираса Рудры") == "Лата"
    assert category_for("Кольчужная броня", "Рукавицы Рудры") == "Кольчуга"
    assert category_for("Кожаная броня", "Дублет Рудры") == "Кожа"
    assert category_for("Тканая броня", "Туника Рудры") == "Ткань"
    assert category_for("Меч", "Клинок Рудры") == "Оружие"
    assert category_for("Лук", "Длинный лук Рудры") == "Оружие"
    assert category_for("", "Чешуйчатый щит Рудры") == "Щиты"
    assert category_for("", "Крылья Рудры") == "Крылья"
    assert category_for("", "Ящик с ядром крыльев рудры") == "Крылья"
    assert category_for("[Титулы]", "[Ивент] [Свиток титула] Победитель") == "Прочее"
