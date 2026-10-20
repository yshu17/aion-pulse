"""SN-7: the user's own schedule changes — added, edited and removed events — kept apart from data/schedule.json."""

import json

from core.schedule.schedule_custom import Custom, check, event_key

BASE = [{"day": "mon", "start": "02:00", "end": "04:00", "name": "Дер", "kind": "Дер"},
        {"day": "wed", "start": "20:00", "end": "21:00", "name": "1x1", "kind": "Арены"}]


def test_added_events_join_the_schedule_and_are_saved(tmp_path):
    path = tmp_path / "schedule_custom.json"
    custom = Custom.load(path)
    mine = {"day": "fri", "start": "19:30", "end": "20:30", "name": "Рейд гильдии"}
    custom.add(mine)
    assert custom.merge(BASE)[-1] == {**mine, "kind": "Свои"}  # own events have their own kind for the filter
    again = Custom.load(path)
    assert again.merge(BASE) == custom.merge(BASE)


def test_removing_a_data_event_hides_it_and_removing_an_own_event_drops_it(tmp_path):
    custom = Custom.load(tmp_path / "c.json")
    custom.remove(BASE[0])
    assert custom.merge(BASE) == [BASE[1]]
    mine = {"day": "fri", "start": "19:30", "end": "20:30", "name": "Рейд"}
    custom.add(mine)
    custom.remove({**mine, "kind": "Свои"})
    assert custom.merge(BASE) == [BASE[1]]
    assert custom.data["removed"] == [event_key(BASE[0])]  # an own event leaves no trace


def test_edit_replaces_the_event():
    custom = Custom(None)
    custom.edit(BASE[1], {"day": "wed", "start": "20:30", "end": "21:30", "name": "1x1"})
    merged = custom.merge(BASE)
    assert [e["start"] for e in merged if e["name"] == "1x1"] == ["20:30"]


def test_check_explains_what_is_wrong():
    assert check({"day": "mon", "start": "19:00", "end": "20:00", "name": "Рейд"}) == ""
    assert "время" in check({"day": "mon", "start": "25:00", "end": "20:00", "name": "Рейд"})
    assert "название" in check({"day": "mon", "start": "19:00", "end": "20:00", "name": "  "})
    assert "день" in check({"day": "xyz", "start": "19:00", "end": "20:00", "name": "Рейд"})
    assert check({"day": "mon", "start": "22:00", "end": "24:00", "name": "Поздно"}) == ""  # 24:00 ends the day


def test_a_broken_file_gives_no_changes(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{oops", encoding="utf-8")
    assert Custom.load(path).merge(BASE) == BASE
    path.write_text(json.dumps({"added": "x"}), encoding="utf-8")
    assert Custom.load(path).merge(BASE) == BASE


def test_one_event_can_be_added_to_several_days(tmp_path):
    """«На все дни»: a single add with days=[...] makes one event per day, each removable separately."""
    custom = Custom.load(tmp_path / "c.json")
    custom.add_days({"start": "19:00", "end": "20:00", "name": "Рейд"}, ["mon", "wed", "fri"])
    days = sorted(e["day"] for e in custom.merge([]))
    assert days == ["fri", "mon", "wed"]
    custom.remove({"day": "wed", "start": "19:00", "end": "20:00", "name": "Рейд", "kind": "Свои"})
    assert sorted(e["day"] for e in custom.merge([])) == ["fri", "mon"]
