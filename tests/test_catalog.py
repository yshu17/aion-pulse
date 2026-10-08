from watcher.catalog import WatchItem, load_item_names, load_watch_items, resource_root


def test_load_item_names(tmp_path):
    path = tmp_path / "item_names.tsv"
    path.write_text("100000893\tКлинок Рудры\n100001081\tМеч Фланаса\n\nbroken line\n", encoding="utf-8")
    assert load_item_names(path) == {"100000893": "Клинок Рудры", "100001081": "Меч Фланаса"}


def test_load_item_names_missing_file(tmp_path):
    assert load_item_names(tmp_path / "nope.tsv") == {}


def test_load_watch_items(tmp_path):
    path = tmp_path / "watch_items.csv"
    path.write_text("id,name,level\n100000893,Клинок Рудры,55\n100001081,Меч Фланаса,55\n", encoding="utf-8")
    assert load_watch_items(path) == [
        WatchItem(id="100000893", name="Клинок Рудры", level=55, category="Прочее"),
        WatchItem(id="100001081", name="Меч Фланаса", level=55, category="Прочее"),
    ]


def test_load_watch_items_missing_file(tmp_path):
    assert load_watch_items(tmp_path / "nope.csv") == []


def test_bundled_data_present():
    data = resource_root() / "data"
    items = load_watch_items(data / "watch_items.csv")
    assert len(items) == 49
    names = load_item_names(data / "item_names.tsv")
    assert names["100000893"] == "Клинок Рудры"
    missing = [item.id for item in items if not (data / "icons" / f"{item.id}.png").is_file()]
    assert missing == ["187000018"]  # Крылья Рудры: the site has no icon (404), app draws a placeholder


def test_category_for():
    from watcher.catalog import category_for

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


def test_load_watch_items_reads_category(tmp_path):
    path = tmp_path / "watch_items.csv"
    path.write_text("id,name,level,category\n1,Кираса Рудры,55,Лата\n2,Без категории,55,\n", encoding="utf-8")
    items = load_watch_items(path)
    assert [i.category for i in items] == ["Лата", "Прочее"]


def test_bundled_watch_list_has_wings_and_categories():
    from watcher.catalog import CATEGORY_ORDER

    items = {i.id: i for i in load_watch_items(resource_root() / "data" / "watch_items.csv")}
    assert items["187000018"].name == "Крылья Рудры"
    assert items["187000018"].category == "Крылья"
    assert items["110600968"].category == "Лата"
    assert all(i.category in CATEGORY_ORDER for i in items.values())
