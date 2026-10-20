from core.chat.segments import Segment, message_segments
from core.chat.status import GAME_OFF, empty_feed, search_hint, status_chip, watching_status
from core.map.zones import enclosing_spawn_circle
from core.notify.notices import release_notice, route_action, schedule_check_notice
from core.text import metres_text, plural, split_keywords


def test_message_segments_mark_items_places_and_hits():
    text = "wts [Кираса Рудры] и [Хлам] у ⟪Место · Келькмарос¦220070000 1 2⟫"
    segments = message_segments(text, ["wts"], {"Кираса Рудры": "7"}, {"7": "legend"})
    assert segments == [
        Segment("wts", hit=True), Segment(" "),
        Segment("<Кираса Рудры>", "item", False, "7", "legend"),
        Segment(" и [Хлам] у "),  # an item without a tooltip stays text
        Segment("<Место · Келькмарос>", "place", place=("220070000", 1.0, 2.0)),
        Segment(""),
    ]
    rudra = message_segments("[Меч Рудры]", ["меч"])
    assert rudra[1] == Segment("<Меч Рудры>", "item", True)  # «Рудр» is shown even without a tooltip


def test_status_texts_and_chip_kinds():
    assert status_chip(watching_status("C:/Chat.log", "нет ключевых слов")) == ("Слежу  ·  нет ключевых слов", "live")
    assert status_chip(GAME_OFF) == ("Игра не запущена", "warn")
    assert status_chip("Ошибка: очень длинное описание ошибки") == ("Ошибка: очень длинн…", "error")
    assert status_chip("Остановлен") == ("Не слежу", "idle")


def test_search_hint_and_empty_feed():
    assert search_hint("or", [], []) == "нет ключевых слов, не отмечены предметы"
    assert search_hint("or", ["wts"], []) == "" and search_hint("and", ["wts"], []) == "не отмечены предметы"
    assert empty_feed(False, "or", ["a", "b"], ["1"]) == ("Нажми Start — здесь появятся совпадения",
                                                          "Ищу: 2 слова, 1 предмет")
    assert empty_feed(True, "items", [], [])[1] == "Сейчас не отмечены предметы"


def test_release_notice_offers_install_only_when_possible():
    assert release_notice(None, True, "1.2.0", "") is None
    assert release_notice(("v1.2.0", "u"), True, "1.2.0", "") is None  # not newer
    assert release_notice(("v1.3.0", "u"), True, "1.2.0", "v1.3.0") is None  # already dismissed
    notice = release_notice(("v1.3.0", "u"), True, "1.2.0", "")
    assert [a for a, _ in notice.actions] == ["install", "release", "accept"]
    assert [a for a, _ in release_notice(("v1.3.0", "u"), False, "1.2.0", "").actions] == ["release", "accept"]


def test_schedule_check_notice():
    assert schedule_check_notice("err", "timeout", "a", "", manual=False) is None
    assert schedule_check_notice("err", "timeout", "a", "", manual=True).kind == "warning"
    assert schedule_check_notice("ok", "a", "a", "", manual=True).title == "Расписание актуально"
    changed = schedule_check_notice("ok", "b", "a", "", manual=False)
    assert changed.title == "Расписание на сайте обновилось" and changed.actions[0][0] == "site"


def test_route_action_tells_release_schedule_and_chat_buttons_apart():
    assert route_action("install", 5, 5, None) == "install"
    assert route_action("install", 6, 5, None) == "open"
    assert route_action("accept", 5, 5, 9) == "release_seen"
    assert route_action("accept", 9, 5, 9) == "schedule_seen"
    assert route_action("accept", 3, 5, 9) == "accept_alerts"
    assert route_action("retry", 3, None, None) == "retry" and route_action("site", 1, None, None) == "open_site"


def test_text_helpers_and_spawn_circle():
    assert plural(21, "слово", "слова", "слов") == "21 слово" and plural(12, "a", "b", "c") == "12 c"
    assert split_keywords(" хил,  ММК ,,") == ["хил", "ММК"]
    assert metres_text(384.4) == "384 м" and metres_text(1600) == "1.6 км"
    assert enclosing_spawn_circle([]) is None
    cx, cy, r = enclosing_spawn_circle([[(0, 0), (100, 0)]])
    assert (cx, cy) == (50, 0) and r == 62
