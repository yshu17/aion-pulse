from core.items.browser import ALL_TYPES, PINNED_GROUP, ItemBrowser, ItemFilter
from core.items.catalog import WatchItem

ITEMS = [
    WatchItem("1", "Кираса Рудры", 55, "Лата", "legend"),
    WatchItem("2", "Меч Фланаса", 55, "Оружие", "legend", kind="Меч"),
    WatchItem("3", "Латный шлем", 50, "Лата", "epic"),
    WatchItem("4", "Кинжал героя", 52, "Оружие", "unique", kind="Кинжал"),
    WatchItem("5", "Кольчуга героя", 52, "Кольчуга", "epic"),
]


def browser(**kwargs):
    return ItemBrowser(ITEMS, **kwargs)


def test_pinned_gear_goes_to_its_own_section_first_then_the_catalog_order():
    b = browser()
    assert list(b.groups) == [PINNED_GROUP, "Лата", "Кольчуга", "Оружие"]
    assert b.visible == ["1", "2", "3", "5", "4"]


def test_filter_by_grade_level_and_type_hides_items_but_keeps_them_checked():
    b = browser(checked=["3", "4"])
    b.set_filter(ItemFilter({"epic"}, 0, 0, "Лата"))
    assert b.visible == ["3"]
    assert b.checked_ids() == ["3", "4"]  # the filtered-out «4» stays watched
    b.set_filter(ItemFilter(set(), 52, 55, "Оружие: Кинжал"))
    assert b.visible == ["4"]


def test_set_all_and_set_group_act_on_shown_items_only():
    b = browser()
    b.set_filter(ItemFilter(set(), 0, 0, "Оружие"))
    b.set_all(True)
    assert b.checked == {"2", "4"}
    assert b.group_checked("Оружие") and b.group_checked(PINNED_GROUP)  # the Flanas sword sits in the pinned section
    b.set_group("Оружие", False)  # only the items of that section: the pinned «2» stays
    b.toggle_item("1")
    assert b.checked == {"1", "2"}


def test_search_needs_every_word_a_number_matches_the_level_and_steps_around():
    b = browser()
    assert b.search("кираса рудр") == 1 and b.current_match() == "1"
    assert b.search("героя") == 2
    assert b.current_match() == "5"  # section order: Кольчуга before Оружие
    assert [b.step(1), b.step(1), b.step(-1)] == ["4", "5", "4"]  # wraps around
    assert b.search("52") == 2  # the level
    assert b.search("") == 0 and b.step(1) is None


def test_a_match_unfolds_its_section_and_folding_toggles():
    b = browser(collapsed=["Лата"])
    assert b.collapsed == ["Лата"]
    assert b.expand_for("3") is True and b.collapsed == [] and b.expand_for("3") is False
    b.toggle_collapsed("Оружие")
    b.toggle_collapsed("Оружие")
    assert b.collapsed == []


def test_grade_chips_toggle_to_an_empty_set_when_every_grade_is_shown_again():
    b = browser()
    assert b.chip_state("epic") == "on" and b.chip_state("epic", enabled=False) == "disabled"
    b.set_filter(b.toggle_grade("epic"))  # all shown -> hide «epic»
    assert "epic" not in b.filter.grades and b.chip_state("epic") == "off"
    b.set_filter(b.toggle_grade("epic"))  # show it again -> every grade shown = no filter
    assert b.filter.grades == set()


def test_level_and_type_boxes_swap_a_reversed_range_and_read_all_types_as_no_type():
    b = browser()
    f = b.with_levels_type(55, 50, ALL_TYPES)
    assert (f.level_min, f.level_max, f.type) == (50, 55, "")
    assert b.type_choices()[0] == ALL_TYPES and "Оружие: Меч" in b.type_choices()
    assert not ItemFilter().active and ItemFilter(type="Лата").active
