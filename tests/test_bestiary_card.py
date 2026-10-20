from core.bestiary.card import (drops_empty_text, drops_note, filter_drops, filter_stock, locations_text, overview_rows,
                                overview_text, place_counts, points_from_text, stock_note)

DETAIL = {
    "level": 55, "rank": "Элитный", "stats": {"HP": 120000}, "race": "Балаур", "title": "Страж", "description": "Сторожит.",
    "points": [{"map_id": "2"}, {"map_id": "1"}, {"map_id": "2"}],
    "drops": [{"name": "Кираса Рудры"}, {"name": "Меч"}],
    "stock": [{"name": "Зелье", "group": "Расходники"}, {"name": "Свиток", "group": "Свитки"}],
    "kb_status": "loaded", "points_from": "Страж леса",
}


def test_overview_rows_and_text():
    assert overview_rows(DETAIL) == [("Уровень", 55), ("Ранг", "Элитный"), ("HP", 120000), ("Принадлежность", "Другие"),
                                     ("Вид", "Балаур")]
    assert overview_text(DETAIL) == "Страж\nСторожит.\nТорговые разделы: Расходники, Свитки"
    assert overview_rows({})[0] == ("Уровень", "Не указан") and overview_text({}) == ""


def test_places_are_counted_per_zone_and_sorted_by_name():
    assert place_counts(DETAIL, {"1": "Ингисон", "2": "Гелькмарос"}) == [("2", 2), ("1", 1)]
    assert points_from_text(DETAIL) == "Места взяты у одноимённой записи «Страж леса»."
    assert locations_text({"kb_locations": [{"name": "Бездна"}]}) == "По базе KB: Бездна"
    assert locations_text({}) == "Точки появления в файлах клиента не найдены."


def test_drops_and_stock_filters_and_notes():
    assert [i for i, _ in filter_drops(DETAIL, " рудр ")] == [0]
    assert drops_note(1, DETAIL) == "Показано 1 из 2. Шансы выпадения не указаны."
    assert drops_note(0, {"kb_status": "loaded"}) == "В профиле нет списка добычи."
    assert drops_empty_text({}) == "Сведения о добыче пока не загружены."
    assert [i for i, _ in filter_stock(DETAIL, "свитки")] == [1]
    assert stock_note(1, 2).startswith("Показано 1 из 2") and stock_note(0, 0).startswith("Для этого NPC")
