import tkinter as tk

import pytest

from watcher.feed import MatchFeed
from watcher.parser import ChatMessage


@pytest.fixture
def root():
    r = tk.Tk()
    r.geometry("900x500")
    yield r
    r.destroy()


def msg(nick, text, time="2026.10.08 18:43:17"):
    return ChatMessage(time=time, nick=nick, text=text, raw="")


def lines(feed):
    return [line.rstrip("\t") for line in feed.text.get("1.0", "end").splitlines() if line.strip()]


def make(root, **kw):
    feed = MatchFeed(root, on_accept=kw.pop("on_accept", lambda _id: None), **kw)
    feed.pack(fill="both", expand=True)
    root.update()
    return feed


def test_rows_append_at_bottom(root):
    feed = make(root)
    feed.add(msg("A", "first"), ["first"])
    feed.add(msg("B", "second"), ["second"])
    rows = lines(feed)
    assert rows[0].endswith("A: first") and rows[1].endswith("B: second")


def test_few_rows_sit_at_the_bottom_like_game_chat(root):
    feed = make(root)
    feed.add(msg("A", "only"), ["only"])
    root.update()
    _x, y, _w, h, _base = feed.text.dlineinfo("end-2l")  # the row's line
    assert y + h > feed.text.winfo_height() * 0.8


def test_pending_row_has_right_aligned_checkbox_without_label_and_countdown(root):
    accepted = []
    feed = make(root, on_accept=accepted.append)
    feed.add(msg("A", "wts"), ["wts"], alert_id=7)
    box = feed.boxes[7]
    assert box.cget("text") == ""
    root.update()
    text_right = feed.text.winfo_rootx() + feed.text.winfo_width()
    assert text_right - 80 < box.winfo_rootx() + box.winfo_width() <= text_right  # fully visible
    feed.set_countdown({7: 27.2})
    assert feed.countdowns[7].cget("text") == "28 с"
    styles = {str(box.cget("style"))}
    feed.blink()
    styles.add(str(box.cget("style")))
    assert len(styles) == 2  # the checkbox itself blinks
    box.invoke()
    assert accepted == [7]


def test_long_row_keeps_checkbox_on_its_first_line_at_right_edge(root):
    feed = make(root)
    feed.add(msg("A", "очень длинное сообщение " * 12), ["wts"], alert_id=1)
    root.update()
    holder = feed.boxes[1].master
    _x, line_y, _w, line_h, _b = feed.text.dlineinfo("a1.first")
    assert abs(holder.winfo_y() - line_y) < line_h
    right_edge = holder.winfo_x() + holder.winfo_width()
    assert feed.text.winfo_width() - 40 < right_edge <= feed.text.winfo_width()


def test_row_colors_pending_accepted_missed(root):
    from watcher.feed import ACCEPTED_BG, MISSED_BG

    feed = make(root)
    feed.add(msg("A", "wts"), ["wts"], alert_id=1)
    feed.add(msg("B", "wts"), ["wts"], alert_id=2)
    feed.mark(1, "accepted")
    feed.mark(2, "missed")
    assert "accepted" in feed.text.tag_names("a1.first")
    assert "missed" in feed.text.tag_names("a2.first")
    assert feed.text.tag_cget("accepted", "background") == ACCEPTED_BG
    assert feed.text.tag_cget("missed", "background") == MISSED_BG


def test_mark_accepted_and_missed_stop_blinking(root):
    feed = make(root)
    feed.add(msg("A", "wts"), ["wts"], alert_id=1)
    feed.add(msg("B", "wts"), ["wts"], alert_id=2)
    feed.mark(1, "accepted")
    assert str(feed.boxes[1].cget("state")) == "disabled"
    assert feed.countdowns[1].cget("text") == ""
    feed.mark(2, "missed")
    assert feed.countdowns[2].cget("text") == "пропущено"
    assert not feed.text.tag_ranges("blink")
    style = str(feed.boxes[1].cget("style"))
    feed.blink()
    assert str(feed.boxes[1].cget("style")) == style  # finished rows no longer blink


def test_old_rows_are_trimmed(root):
    feed = make(root, max_rows=3)
    for i in range(5):
        feed.add(msg(f"N{i}", "wts"), ["wts"], alert_id=i)
    rows = lines(feed)
    assert len(rows) == 3 and rows[0].endswith("N2: wts")
    assert set(feed.boxes) == {2, 3, 4}


def test_item_links_take_grade_colour(root):
    feed = make(root, spec_items={"Меч Сематы": "1", "Клинок Рудры": "2"}, grades={"1": "legend", "2": "epic"})
    feed.add(msg("S", "wts [Меч Сематы] [Клинок Рудры] [Камень]"), [])
    text = feed.text
    start, _end = text.tag_ranges("item_1")
    assert "grade_legend" in text.tag_names(start)
    start, _end = text.tag_ranges("item_2")
    assert "grade_epic" in text.tag_names(start)
    assert "[Камень]" in text.get("1.0", "end")  # unknown, non-Rudra links stay plain


def test_place_links_are_styled(root):
    feed = make(root)
    feed.add(msg("S", "Форт ⟪Место · Келькмарос⟫ го"), [])
    text = feed.text
    start, end = text.tag_ranges("place")
    assert text.get(start, end) == "<Место · Келькмарос>"


def test_copy_selection_and_whole_message(root):
    feed = make(root)
    feed.add(msg("Seller", "wts ⟪Место · Келькмарос⟫ 5кк"), [])
    feed.add(msg("Buyer", "wtb ммк"), [], quiet=True)
    text = feed.text
    line = text.search("Seller", "1.0")
    text.tag_add("sel", line, f"{line}+6c")
    assert feed.copy.copy_selection() == "Seller"
    assert root.clipboard_get() == "Seller"
    assert feed.copy.copy_line(line) == "18:43:17  Seller: wts <Место · Келькмарос> 5кк"
    buyer = text.search("Buyer", "1.0")
    assert feed.copy.copy_line(buyer) == "18:43:17  Buyer: wtb ммк"  # «уже принято» note dropped
    feed.copy.select_all()
    assert "Seller" in feed.copy.selection() and "Buyer" in feed.copy.selection()


def test_ctrl_c_copies_on_any_layout(root):
    feed = make(root)
    feed.add(msg("Seller", "wts"), [])
    text = feed.text
    text.tag_add("sel", "2.0", "2.5")
    event = type("E", (), {"keycode": 67, "keysym": "Cyrillic_es"})()
    assert feed.copy._on_ctrl_key(event) == "break"
    assert root.clipboard_get() == text.get("2.0", "2.5")


def test_click_on_place_link_reports_coordinates(root):
    opened = []
    feed = make(root, on_place=lambda *args: opened.append(args))
    feed.add(msg("S", "го ⟪Место · Келькмарос¦220070000 2010.1 1315.8⟫"), [])
    text = feed.text
    start, end = text.tag_ranges("place")
    assert text.get(start, end) == "<Место · Келькмарос>"
    root.deiconify()
    root.update()
    x, y, width, height = text.bbox(f"{start}+2c")
    # Tk tags see the pointer through the «current» mark, which a motion event sets
    text.event_generate("<Motion>", x=x + width // 2, y=y + height // 2)
    text.event_generate("<Button-1>", x=x + width // 2, y=y + height // 2)
    root.update()
    assert opened == [("220070000", 2010.1, 1315.8, "Место · Келькмарос")]


def test_match_is_quiet_orange_bold_with_a_stripe_on_its_line(root):
    """UI/UX item 9: no solid orange block — orange bold words on a quiet ground and a stripe at the line's left."""
    from watcher import theme

    feed = make(root)
    feed.add(msg("Leader", "ммк 1/12 нужен хил"), ["хил"])
    feed.add(msg("Other", "просто чат"), [])
    text = feed.text
    assert text.tag_cget("hit", "background") == theme.ACCENT_SUBTLE
    assert text.tag_cget("hit", "foreground") == theme.ACCENT
    assert text.tag_cget("hitline", "lmargincolor") == theme.ACCENT
    first, second = [i for i in range(1, 6) if text.get(f"{i}.0", f"{i}.end").strip()][:2]
    assert "hitline" in text.tag_names(f"{first}.5") and "hitline" not in text.tag_names(f"{second}.5")
    assert "row" in text.tag_names(f"{second}.5")  # same left margin, so plain rows do not shift
    assert text.tag_cget("row", "lmargin1") == text.tag_cget("hitline", "lmargin1")


def test_empty_feed_says_what_will_appear_until_the_first_row(root):
    feed = make(root)
    feed.show_empty("magnifying-glass", "Нажми Start — здесь появятся совпадения", "Ищу: 2 слова, 0 предметов")
    root.update()
    assert feed.empty.shown and feed.empty.title.cget("text").startswith("Нажми Start")
    assert feed.empty.picture.cget("image")  # the 32 px Phosphor picture
    feed.add(msg("Nick", "ищу хила"), ["хил"])
    assert not feed.empty.shown
    feed.show_empty("magnifying-glass", "Слежу — совпадений пока нет")  # rows exist: the empty state stays away
    assert not feed.empty.shown


def test_loading_state_animates_its_dots(root):
    feed = make(root)
    feed.show_empty("hourglass-medium", "Читаю историю за 15 мин…", loading=True)
    texts = set()
    for _ in range(4):
        texts.add(feed.empty.title.cget("text"))
        feed.empty._stop_dots()
        feed.empty._tick_dots()
    assert all(t.startswith("Читаю историю за 15 мин") for t in texts)
    assert len(texts) >= 3  # «», «.», «..», «...» — the line breathes
    feed.add_note("— выше история —")
    assert not feed.empty.shown and feed.empty._after is None


def test_warning_banner_keeps_action_visible_at_narrow_width(root):
    root.geometry("520x350")
    feed = make(root)
    feed.show_banner("Игра не запущена. После запуска Aion нажми «Проверить снова».",
                     "Проверить снова", lambda: None)
    root.update()
    assert feed.banner_button.winfo_ismapped()
    assert feed.banner_button.winfo_x() + feed.banner_button.winfo_width() <= feed.banner.winfo_width()
    assert feed.banner_label.winfo_height() > 20  # long warning wraps instead of pushing the action away
