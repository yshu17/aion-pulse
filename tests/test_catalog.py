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
        WatchItem(id="100000893", name="Клинок Рудры", level=55),
        WatchItem(id="100001081", name="Меч Фланаса", level=55),
    ]


def test_load_watch_items_missing_file(tmp_path):
    assert load_watch_items(tmp_path / "nope.csv") == []


def test_bundled_data_present():
    data = resource_root() / "data"
    items = load_watch_items(data / "watch_items.csv")
    assert len(items) == 48
    names = load_item_names(data / "item_names.tsv")
    assert names["100000893"] == "Клинок Рудры"
    assert all((data / "icons" / f"{item.id}.png").is_file() for item in items)
