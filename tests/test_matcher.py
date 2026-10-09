import pytest

from watcher.matcher import Matcher, highlight_segments, normalize
from watcher.parser import ChatMessage


def msg(text, nick="Nick"):
    return ChatMessage(time="2026.10.08 18:00:00", nick=nick, text=text, raw="")


def test_normalize():
    assert normalize("ЕщЁ MMK") == "еще mmk"


def test_case_insensitive_cyrillic():
    assert Matcher(["ммк"]).check(msg("WTB ММК 2.2кк"), 0) == ["ммк"]


def test_yo_equals_e_both_ways():
    assert Matcher(["ещё"]).check(msg("нужен ЕЩЕ хил"), 0) == ["ещё"]
    assert Matcher(["еще"]).check(msg("нужен ещё хил"), 0) == ["еще"]


def test_returns_all_matched_keywords():
    assert Matcher(["хил", "чант", "глад"]).check(msg("Хил чант кожа"), 0) == ["хил", "чант"]


def test_no_match():
    assert Matcher(["хил"]).check(msg("WTB MMK"), 0) == []


def test_blank_and_duplicate_keywords_dropped():
    assert Matcher(["", "  ", " Хил ", "хил"]).keywords == ["Хил"]


def test_nick_is_not_searched():
    assert Matcher(["zdravie"]).check(msg("Удасы по всем рб", nick="Zdravie"), 0) == []


def test_cooldown_blocks_repeat_then_allows():
    m = Matcher(["хил"], cooldown_sec=60)
    assert m.check(msg("Хил нужен"), 0) == ["хил"]
    assert m.check(msg("Хил нужен"), 30) == []
    assert m.check(msg("ХИЛ нужен"), 59.9) == []
    assert m.check(msg("Хил нужен"), 61) == ["хил"]


def test_other_nick_is_new_alert():
    m = Matcher(["хил"], cooldown_sec=60)
    assert m.check(msg("Хил нужен", nick="A"), 0) == ["хил"]
    assert m.check(msg("Хил нужен", nick="B"), 1) == ["хил"]


def test_set_keywords_live():
    m = Matcher(["хил"])
    m.set_keywords(["чант"])
    assert m.keywords == ["чант"]
    assert m.check(msg("хил чант"), 0) == ["чант"]


def test_highlight_segments():
    assert highlight_segments("WTB MMK sm", ["mmk"]) == [
        ("WTB ", False),
        ("MMK", True),
        (" sm", False),
    ]


def test_highlight_overlap_and_repeats():
    assert highlight_segments("abcd ab", ["ab", "bc"]) == [
        ("abc", True),
        ("d ", False),
        ("ab", True),
    ]


def test_highlight_empty():
    assert highlight_segments("", ["x"]) == []
    assert highlight_segments("текст", []) == [("текст", False)]


def item_msg(text, item_ids, nick="Nick"):
    return ChatMessage(time="2026.10.08 18:00:00", nick=nick, text=text, raw="", item_ids=item_ids)


def test_watched_item_id_matches_and_returns_name():
    m = Matcher([], watch_items={"100000893": "Клинок Рудры"})
    assert m.check(item_msg("wts [Клинок Рудры]", ("100000893",)), 0) == ["Клинок Рудры"]


def test_unwatched_item_id_does_not_match():
    m = Matcher([], watch_items={"100000893": "Клинок Рудры"})
    assert m.check(item_msg("wts [item]", ("168000066",)), 0) == []


def test_item_and_keyword_hits_combined():
    m = Matcher(["wts"], watch_items={"100000893": "Клинок Рудры"})
    assert m.check(item_msg("WTS [Клинок Рудры]", ("100000893",)), 0) == ["wts", "Клинок Рудры"]


def test_no_watched_items_falls_back_to_keywords():
    m = Matcher(["рудры"])
    assert m.check(item_msg("wts [Клинок Рудры]", ("100000893",)), 0) == ["рудры"]


def test_set_watch_items_live():
    m = Matcher([])
    m.set_watch_items({"100001081": "Меч Фланаса"})
    assert m.check(item_msg("[Меч Фланаса]", ("100001081",)), 0) == ["Меч Фланаса"]
    m.set_watch_items({})
    assert m.check(item_msg("[Меч Фланаса]", ("100001081",), nick="B"), 0) == []


def test_item_hit_respects_cooldown():
    m = Matcher([], cooldown_sec=60, watch_items={"100000893": "Клинок Рудры"})
    msg = item_msg("[Клинок Рудры]", ("100000893",))
    assert m.check(msg, 0) == ["Клинок Рудры"]
    assert m.check(msg, 10) == []


ITEMS = {"100000893": "Клинок Рудры"}
WORD_ONLY = ("wts ммк", ())
ITEM_ONLY = ("[Клинок Рудры]", ("100000893",))
BOTH = ("wts [Клинок Рудры]", ("100000893",))


def run(mode, case, nick="N"):
    text, ids = case
    return Matcher(["wts"], watch_items=ITEMS, mode=mode).check(item_msg(text, ids, nick), 0)


@pytest.mark.parametrize("mode, word_only, item_only, both", [
    ("words", ["wts"], [], ["wts"]),
    ("items", [], ["Клинок Рудры"], ["Клинок Рудры"]),
    ("and", [], [], ["wts", "Клинок Рудры"]),
    ("or", ["wts"], ["Клинок Рудры"], ["wts", "Клинок Рудры"]),
])
def test_search_modes(mode, word_only, item_only, both):
    assert Matcher([]).mode == "or"  # default
    assert run(mode, WORD_ONLY) == word_only
    assert run(mode, ITEM_ONLY) == item_only
    assert run(mode, BOTH) == both


def test_set_mode_live_and_unknown_mode_falls_back_to_or():
    m = Matcher(["wts"], watch_items=ITEMS, mode="bogus")
    assert m.mode == "or"
    m.set_mode("and")
    assert m.check(item_msg(*WORD_ONLY), 0) == []
