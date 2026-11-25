"""tools/build_consumables.py: the stat buffs of food and drinks read from the items' cards.

The cases are the ones the audit of 25.11.2026 found broken: «Физ. крит.» was lost, «Виноградный омлет» and «мясо эльрока»
became drinks, «Маг. защита%» stood apart from «Маг. защита», «Восст. HP» came out as «HP».
"""
import pytest

from tools.build_consumables import UnknownStat, kind_of, merge_same, parse_card, use_level


def test_stats_and_duration_from_the_card_text():
    found = parse_card("Вино с приятным ароматом. Физ. атака +2. Сила магии +10. Время действия: 30 мин.")
    assert found == {"stats": [["Физ. атака", 2, False], ["Сила магии", 10, False]], "unknown": [], "minutes": 30}


def test_every_bonus_is_kept_physical_crit_too():
    found = parse_card("Физ. крит. +10. Точность +10. Уклонение +5. Время действия: 45 мин.")
    assert found["stats"] == [["Физ. крит.", 10, False], ["Точность", 10, False], ["Уклонение", 5, False]]


def test_the_sites_percent_before_the_plus_is_no_percent_and_a_bonus_without_a_number_is_named():
    found = parse_card("Физ. крит% +10. Маг. защита% +5. ElementalDefendAll% +10. Время полета% +. Время действия: 30 мин.")
    assert found["stats"] == [["Физ. крит.", 10, False], ["Маг. защита", 5, False], ["Защ. от стихий", 10, False]]
    assert found["unknown"] == ["Время полета"]


def test_words_before_the_name_do_not_cut_it():
    found = parse_card("Отнесите Лисичке подарок. При использовании Восст. HP +2. Время действия: 30 мин.")
    assert found["stats"] == [["Восст. HP", 2, False]]


def test_percents_hours_and_the_other_order_of_the_time():
    assert parse_card("Скорость атаки +5%. Время действия: 1 ч.")["stats"] == [["Скорость атаки", 5, True]]
    assert parse_card("Макс. HP +40. В течение 30 мин. Нельзя вместе с другими.")["minutes"] == 30


def test_a_candys_list_by_commas_and_its_words_for_the_same_stats():
    found = parse_card("Конфета удачи. В течение 60 мин. Атака +2, Точн. маг. +48, Макс. HP +220, Скор. движ. +3%, Скор. атаки +3%, Скор. магии +3%.")
    assert found["stats"] == [["Физ. атака", 2, False], ["Маг. точность", 48, False], ["Макс. HP", 220, False],
                              ["Скорость", 3, True], ["Скорость атаки", 3, True], ["Скорость магии", 3, True]]
    assert found["minutes"] == 60


def test_a_bonus_with_a_name_the_collector_does_not_know_stops_it():
    with pytest.raises(UnknownStat):
        parse_card("Удача +7. Время действия: 30 мин.")


def test_a_card_without_a_lasting_stat_is_no_buff():
    assert parse_card("Восстанавливает 4000 DP.") is None
    assert parse_card("Макс. HP +40.") is None  # no duration: not a lasting buff
    assert parse_card("Из-за яда может заболеть живот. Время действия: 30 мин.") is None


def test_the_kind_comes_from_the_clients_picture_not_from_letters_in_the_name():
    assert kind_of("icon_item_dish04") == "food"  # «Виноградный омлет»
    assert kind_of("icon_item_dish09") == "food"  # «Тушеное мясо эльрока»
    assert kind_of("icon_item_drink02") == "drink"
    assert kind_of("icon_item_tea01") == "drink"
    assert kind_of("icon_item_candy02") == "candy"
    assert kind_of("icon_item_fruit01") == "food"


def test_the_level_to_use_it_is_only_what_a_card_says():
    assert use_level({"blocks": [{"kind": "warning", "text": "Можно использовать с 50-го уровня."}]}) == 50
    assert use_level({"blocks": [{"kind": "text", "text": "Физ. атака +2."}]}) is None
    assert use_level(None) is None


def test_items_of_one_name_and_effect_become_one_entry():
    base = {"kind": "food", "stats": [["Макс. HP", 40, False]], "unknown": [], "minutes": 30, "grade": "common", "icon": "i",
            "item_level": 10, "use_level": None}
    merged = merge_same([{"id": 2, "name": "Омлет", **base}, {"id": 1, "name": "Омлет", **base}, {"id": 3, "name": "Суп", **base}])
    assert [(m["id"], m["name"], m["ids"]) for m in merged] == [(1, "Омлет", [1, 2]), (3, "Суп", [3])]
