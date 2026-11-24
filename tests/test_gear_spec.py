"""The equipment card made from the game client's own numbers (core/pulse_db/gear_spec.py)."""

from core.pulse_db.gear_spec import gear_spec

SWORD = {  # the client's record of «Орихалковый меч» (100000339), the fields that matter
    "weapon_type": "1h_sword", "equipment_slots": "main_or_sub", "level": "45", "quality": "common",
    "min_damage": "115", "max_damage": "141", "attack_delay": "1400", "magical_hit_accuracy": "173", "hit_accuracy": "580",
    "critical": "50", "parry": "587", "magical_skill_boost": "0", "bonus_attr1": "critical 19",
    "can_exchange": "TRUE", "can_sell_to_npc": "TRUE",
}


def _grids(spec):
    return [dict(b["pairs"]) for b in spec["blocks"] if b["kind"] == "grid"]


def test_weapon_base_stats_in_the_sites_order_and_wording():
    spec = gear_spec(name="Орихалковый меч", grade="common", fields=SWORD, description="")
    base = [b for b in spec["blocks"] if b["kind"] == "grid"][0]["pairs"]
    assert base == [["Атака", "115-141"], ["Скор. атаки", "1.4"], ["Точн. маг.", "173"], ["Точность", "580"],
                    ["Ф. крит.", "50"], ["Парир.", "587"]]


def test_bonus_stats_from_bonus_attr():
    spec = gear_spec(name="Орихалковый меч", grade="common", fields=SWORD, description="")
    assert _grids(spec)[1] == {"Физ. крит": "+19"}


def test_type_and_level_lines():
    spec = gear_spec(name="Орихалковый меч", grade="common", fields=SWORD, description="")
    assert {"kind": "pairs", "rows": [["Тип", "Меч"]]} in spec["blocks"]
    assert {"kind": "warning", "text": "Можно использовать с 45-го уровня."} in spec["blocks"]
    assert spec["name"] == "Орихалковый меч" and spec["grade"] == "common"


def test_armour_base_stats():
    fields = {"armor_type": "leather", "equipment_slots": "torso", "level": "30", "physical_defend": "120",
              "magical_resist": "40", "dodge": "60", "bonus_attr1": "maxhp 90", "bonus_attr2": "flyspeed 10%"}
    spec = gear_spec(name="Куртка", grade="rare", fields=fields, description="")
    base, bonus = _grids(spec)
    assert list(base.items()) == [("Физ. защита", "120"), ("Маг. сопр.", "40"), ("Уклонение", "60")]
    assert bonus == {"Макс. HP": "+90", "Скор. полёта": "+10%"}
    assert {"kind": "pairs", "rows": [["Тип", "Кожаная броня"]]} in spec["blocks"]


def test_bonus_a_lines_follow_the_bonus_lines_and_negative_stays_negative():
    fields = {"armor_type": "robe", "equipment_slots": "torso", "level": "40", "physical_defend": "50",
              "bonus_attr1": "maxHp 277", "bonus_attr3": "BoostHate -33%", "bonus_attr_a1": "PhysicalCriticalReduceRate 15",
              "bonus_attr_a2": "parry 61", "bonus_attr_b1": "maxmp 30"}
    spec = gear_spec(name="Роба", grade="epic", fields=fields, description="")
    assert [b for b in spec["blocks"] if b["kind"] == "grid"][1]["pairs"] == [
        ["Макс. HP", "+277"], ["Агрессия", "-33%"], ["Блок ф.крит.", "+15"], ["Парир.", "+61"], ["Макс. MP", "+30"]]


def test_unknown_bonus_key_is_left_out_never_raw():
    fields = {"equipment_slots": "neck", "level": "20", "magical_resist": "30", "bonus_attr1": "somethingnew 5",
              "bonus_attr2": "maxmp 50"}
    spec = gear_spec(name="Ожерелье", grade="common", fields=fields, description="")
    assert _grids(spec)[1] == {"Макс. MP": "+50"}


def test_trade_flags_and_description_kept():
    fields = {**SWORD, "can_exchange": "FALSE"}
    spec = gear_spec(name="Меч", grade="common", fields=fields, description="Старый меч стражи.")
    assert {"kind": "props", "lines": ["[Нельзя обменять]"]} in spec["blocks"]
    assert {"kind": "text", "text": "Старый меч стражи.", "style": "normal"} in spec["blocks"]


def test_not_equipment_gives_none():
    assert gear_spec(name="Хлеб", grade="common", fields={"equipment_slots": "none", "level": "10"}, description="") is None


def test_equipment_without_numbers_gives_none():
    fields = {"armor_type": "clothes", "equipment_slots": "torso", "level": "10"}
    assert gear_spec(name="Костюм", grade="common", fields=fields, description="") is None
