"""core/pulse_db/gear.py: the gear calculator's rows from the client's item fields."""

import json

from core.pulse_db.gear import group_of, item_row, slot_of, stat_line


def test_bonus_lines_and_groups():
    assert stat_line("maxHp 407") == ["maxhp", 407, False]
    assert stat_line("flyspeed 10%") == ["flyspeed", 10, True]
    assert stat_line("['maxhp 20") == ["maxhp", 20, False]
    assert stat_line("nonsense") is None
    assert group_of({"weapon_type": "2h_polearm", "equipment_slots": "main"}) == "polearm"
    assert group_of({"equipment_slots": "sub", "name": "shield_n_e1_50a"}) == "shield"
    assert group_of({"armor_type": "plate", "equipment_slots": "torso"}) == "pl_torso"
    assert group_of({"armor_type": "robe", "equipment_slots": "leg"}) == "rb_pants"
    assert group_of({"equipment_slots": "right_or_left_finger"}) == "ring"
    assert slot_of({"equipment_slots": "main_or_sub"}, "sword") == "main_or_sub"
    assert slot_of({}, "pl_shoes") == "shoes"


def test_an_item_row_keeps_its_own_numbers_its_bonus_lines_and_who_wears_it():
    fields = {"weapon_type": "2h_polearm", "equipment_slots": "main", "quality": "epic", "level": "55", "min_damage": "285",
              "max_damage": "531", "attack_delay": "2800", "attack_range": "2.500000", "parry": "1054", "fighter": "55", "knight": "0",
              "race_permitted": "pc_light pc_dark", "bonus_attr1": "maxHp 347", "bonus_attr2": "attackDelay 19%", "no_enchant": "FALSE"}
    row = item_row(101300822, "Копье", "icon", fields, {"count": 5, "bonus": 0})
    assert row[:8] == (101300822, "Копье", "icon", "epic", 55, "main", "polearm", "pc_light,pc_dark")
    assert json.loads(row[8]) == ["fighter"]
    assert json.loads(row[9]) == {"mindamage": 285, "maxdamage": 531, "attackdelay": 2800, "parry": 1054, "attackrange": 2500}
    assert json.loads(row[10]) == [["maxhp", 347, False], ["attackdelay", 19, True]]
    assert row[11:] == (5, 0, 1)
    assert item_row(1, "Костюм", None, {"armor_type": "clothes", "equipment_slots": "torso"}, None) is None
    wing = item_row(2, "Крылья", None, {"armor_type": "clothes", "equipment_slots": "wing", "quality": "epic", "level": "55", "bonus_attr1": "maxfp 80"}, None)
    assert wing is not None and wing[5] == "wing" and wing[6] == "wing"  # the wings are «clothes» in the client, with stats
    assert item_row(3, "Тестовый эпический меч 55-го уровня ([%username])", None, {"weapon_type": "1h_sword", "equipment_slots": "main_or_sub"}, None) is None
