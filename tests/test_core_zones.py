import json

from core.chat.categories import category, is_notice
from core.chat.parser import parse_any_line
from core.map.zones import FILTER_GROUPS, QUEST_TYPES, SHOWN_TYPES, Place, Zone, load_labels, load_zones


def _line(rest):
    return parse_any_line(f"2026.10.20 12:00:00 : {rest}")


def test_chat_categories_by_channel_whisper_and_name_colour():
    assert category(_line("[3.Поиск группы] [charname:A;1 1 1]: ищу")) == "Поиск группы"
    assert category(_line("[1.Общий] [charname:A;1 1 1]: привет")) == "Общий"
    assert category(_line("[charname:A;0.6275 1.0000 0.6275] шепчет: привет")) == "Личное"
    assert category(_line("[charname:A;0.0196 0.7843 0.8431]: в группу")) == "Группа"
    assert category(_line("[2.Торговля] [charname:A;1 1 1]: wts")) is None


def test_notices_are_system_lines_without_combat():
    assert is_notice(_line("Вы получили 100 кинар.")) is True
    assert is_notice(_line("[charname:A;1 1 1]: Вы получили 100 кинар.")) is False  # a player line
    assert is_notice(_line("Бешеный ветер I: Скор. движ. цели Mockoco увеличивается.")) is False


def test_zone_loader_gives_coordinates_labels_and_sides(tmp_path):
    (tmp_path / "k.jpg").write_bytes(b"x")
    (tmp_path / "maps.json").write_text(json.dumps({
        "1": {"file": "k.jpg", "size": 100, "x": [0.1, 5], "y": [0.2, 7], "side": "dark"},
        "2": {"file": "missing.jpg", "size": 100, "x": [1, 0], "y": [1, 0]},
    }), encoding="utf-8")
    (tmp_path / "labels.tsv").write_text("# map\tlevel\tx\ty\ttext\n1\tmain\t10\t20\tЛес|север\n", encoding="utf-8")
    zones = load_zones(tmp_path, {"1": "Келька"})
    assert list(zones) == ["1"]  # a zone without its picture is skipped
    zone = zones["1"]
    assert isinstance(zone, Zone) and zone.name == "Келька" and zone.side == "dark"
    assert zone.to_image(10, 20) == (0.1 * 20 + 5, 0.2 * 10 + 7)
    assert zone.labels[0][2] == "Лес\nсевер"
    assert load_labels(tmp_path / "none.tsv") == {} and load_zones(tmp_path / "none", {}) == {}


def test_filter_groups_cover_the_shown_point_types():
    grouped = {t for _title, types in FILTER_GROUPS.values() for t in types}
    assert grouped == set(SHOWN_TYPES) | set(QUEST_TYPES)  # quest givers have their own menu entry
    assert Place("1", 2.0, 3.0, "Место").note == ""
