import tkinter as tk

import pytest

from watcher import theme
from watcher.catalog import WatchItem
from watcher.itemlist import ROW_H, ItemList


@pytest.fixture
def root():
    r = tk.Tk()
    r.geometry("700x600")
    theme.apply_dark_theme(r)
    yield r
    r.destroy()


def catalog(n_plate=300):
    items = [WatchItem(str(1000 + i), f"Латные сапоги {i}", 50, "Лата", "rare") for i in range(n_plate)]
    items += [
        WatchItem("2001", "Клинок Рудры", 55, "Оружие", "epic"),
        WatchItem("2002", "Меч Фланаса", 55, "Оружие", "epic"),
        WatchItem("2003", "Чешуйчатый меч Рудры", 50, "Оружие", "epic"),
        WatchItem("3001", "Крылья Рудры", 55, "Крылья", "epic"),
        WatchItem("2004", "Меч Сематы", 50, "Оружие", "legend", kind="Меч"),
        WatchItem("2005", "Лук Сематы", 52, "Оружие", "unique", kind="Лук"),
    ]
    return items


def make(root, **kw):
    calls = {"change": 0, "collapse": []}
    items_list = ItemList(
        root,
        kw.pop("items", catalog()),
        on_change=lambda: calls.__setitem__("change", calls["change"] + 1),
        on_collapse=lambda c: calls["collapse"].append(c),
        **kw,
    )
    items_list.pack(fill="both", expand=True)
    root.update()
    return items_list, calls


def drawn_names(lst):
    return {lst.canvas.itemcget(i, "text") for i in lst.canvas.find_withtag("row") if lst.canvas.type(i) == "text"}


def test_draws_only_visible_rows(root):
    lst, _ = make(root, items=catalog(5000))
    texts = [i for i in lst.canvas.find_withtag("row") if lst.canvas.type(i) == "text"]
    assert 0 < len(texts) < 60


def test_search_jumps_to_first_match_and_steps(root):
    lst, _ = make(root)
    assert lst.search("рудр") == 3
    assert lst.current_match() == "2001"
    assert "Клинок Рудры" in drawn_names(lst)
    lst.step(1)
    assert lst.current_match() == "2003"
    lst.step(1)
    assert lst.current_match() == "3001"
    lst.step(1)
    assert lst.current_match() == "2001"  # wraps around
    lst.step(-1)
    assert lst.current_match() == "3001"
    assert lst.count_label.cget("text") == "3 / 3"


def test_search_words_and_level(root):
    lst, _ = make(root)
    assert lst.search("меч рудры") == 1
    assert lst.search("рудры 55") == 2
    assert lst.search("ё нет такого") == 0
    assert lst.count_label.cget("text") == "нет"
    assert lst.search("") == 0
    assert lst.count_label.cget("text") == ""


def test_search_unfolds_collapsed_section(root):
    lst, calls = make(root, collapsed=["Оружие"])
    assert lst.row_top("2004") is None
    lst.search("сематы меч")
    assert "Оружие" not in lst.collapsed
    assert calls["collapse"][-1] == []
    top = lst.row_top("2004")
    first_visible = lst.canvas.canvasy(0)
    assert first_visible <= top <= first_visible + lst.canvas.winfo_height() - ROW_H


def test_enter_in_search_box_searches_then_steps(root):
    lst, _ = make(root)
    lst.search_var.set("рудр")
    lst._on_search_key(type("E", (), {"keysym": "a"})())
    lst.step(1)  # pending search runs first, then moves to the second match
    assert lst.current_match() == "2003"


def test_click_toggles_item_and_group(root):
    lst, calls = make(root, items=catalog(3))
    lst.toggle_item("1000")
    assert lst.checked_ids() == ["1000"] and calls["change"] == 1
    lst.set_group("Лата", True)
    assert lst.group_checked("Лата")
    lst.set_group("Лата", False)
    assert lst.checked_ids() == []
    lst.set_all(True)
    assert len(lst.checked_ids()) == 9


def test_click_on_rows(root):
    lst, calls = make(root, items=catalog(3))
    first_item_y = lst.row_top("1000") + ROW_H // 2
    lst._on_click(type("E", (), {"x": 200, "y": first_item_y})())
    assert lst.checked == {"1000"}
    group_y = lst._tops[lst._rows.index(("group", "Лата"))] + 10
    lst._on_click(type("E", (), {"x": lst.canvas.winfo_width() - 20, "y": group_y})())
    assert lst.group_checked("Лата")
    lst._on_click(type("E", (), {"x": 40, "y": group_y})())
    assert lst.collapsed == ["Лата"] and lst.row_top("1000") is None


def test_disabled_ignores_clicks(root):
    lst, calls = make(root, items=catalog(3))
    lst.set_enabled(False)
    lst._on_click(type("E", (), {"x": 200, "y": lst.row_top("1000") + 5})())
    assert lst.checked == set() and calls["change"] == 0


def test_hover_reports_item(root):
    seen = []
    lst, _ = make(root, items=catalog(3), on_hover=seen.append, on_leave=lambda: seen.append(None))
    lst._on_motion(type("E", (), {"x": 200, "y": lst.row_top("1001") + 5})())
    lst._set_hover(None)
    assert seen == ["1001", None]


def test_rudra_gear_pinned_in_top_section(root):
    lst, _ = make(root)
    assert list(lst.groups)[0] == "Рудра и Фланас"
    assert [i.id for i in lst.groups["Рудра и Фланас"]] == ["2001", "2002", "2003", "3001"]
    assert [i.id for i in lst.groups["Оружие"]] == ["2004", "2005"]
    assert lst.row_top("2001") < lst.row_top("1000")
    lst.toggle_collapsed("Рудра и Фланас")
    lst.search("клинок")
    assert "Рудра и Фланас" not in lst.collapsed and lst.current_match() == "2001"


def test_filter_by_grade_level_and_type(root):
    from watcher.itemlist import ItemFilter

    seen = []
    lst, _ = make(root, on_filter=seen.append)
    assert "Оружие: Меч" in lst.type_choices() and "Лата" in lst.type_choices()
    lst.set_filter(ItemFilter(grades={"epic"}))
    assert set(lst.visible) == {"2001", "2002", "2003", "3001"}
    lst.set_filter(ItemFilter(level_min=51, level_max=54))
    assert lst.visible == ["2005"]
    lst.set_filter(ItemFilter(type="Оружие: Меч"))
    assert lst.visible == ["2004"]
    lst.set_filter(ItemFilter(type="Оружие"))
    assert lst.visible == ["2001", "2002", "2003", "2004", "2005"]  # pinned weapons too
    assert seen[-1].type == "Оружие"
    lst._reset_filter()
    assert len(lst.visible) == 306


def test_search_and_select_all_only_touch_shown_items(root):
    from watcher.itemlist import ItemFilter

    lst, _ = make(root, item_filter=ItemFilter(type="Оружие"))
    assert lst.search("сематы") == 2
    assert lst.search("крылья") == 0  # wings are filtered out by type
    lst.set_all(True)
    assert lst.checked == {"2001", "2002", "2003", "2004", "2005"}
    lst.set_filter(ItemFilter())
    lst.set_all(False)
    assert lst.checked == set()


def test_grade_chips_toggle(root):
    lst, _ = make(root)
    assert lst.grades == ["epic", "unique", "legend", "rare"]
    lst._toggle_grade("rare")
    assert lst.filter.grades == {"epic", "unique", "legend"}
    assert "1000" not in lst.visible
    lst._toggle_grade("rare")
    assert lst.filter.grades == set()  # all on again = no grade filter
