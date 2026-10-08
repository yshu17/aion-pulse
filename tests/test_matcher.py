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
