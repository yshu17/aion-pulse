from watcher.parser import ChatMessage, clean_text, parse_line

CMD_LINE = (
    "2026.10.08 18:43:17 : [3.Поиск группы] [charname:Tiyamate;1.0000 0.6941 0.6941]: "
    "[cmd:Tiyamate;sxFsA1JTuwlRMeXXcsGOGIhtgp+mUuuHulz+ZUdiohM=]WTB MMK 2.2KK SM++++++++++++++ "
)
ITEM_LINE = (
    "2026.10.08 18:42:00 : [3.Поиск группы] [charname:Roflokabanchik;1.0000 0.6941 0.6941]: "
    "wts [item:168000066;ver2;;;][item:168000067;ver2;;;] вставка "
)
PLAIN_LINE = (
    "2026.10.08 18:42:08 : [3.Поиск группы] [charname:Flomaster;1.0000 0.6941 0.6941]: "
    "А ангир будут исправлять? "
)
SYSTEM_LINE = "2026.10.08 18:42:29 : Бешеный ветер I: Скор. движ. цели Mockoco увеличивается. "
OTHER_CHANNEL_LINE = (
    "2026.10.08 18:42:29 : [1.Общий] [charname:Someone;1.0000 1.0000 1.0000]: хил нужен"
)


def test_parses_player_message_and_strips_cmd():
    msg = parse_line(CMD_LINE)
    assert msg == ChatMessage(
        time="2026.10.08 18:43:17",
        nick="Tiyamate",
        text="WTB MMK 2.2KK SM++++++++++++++",
        raw=CMD_LINE,
    )


def test_replaces_item_links():
    msg = parse_line(ITEM_LINE)
    assert msg is not None
    assert msg.nick == "Roflokabanchik"
    assert msg.text == "wts [item][item] вставка"


def test_parses_plain_message():
    msg = parse_line(PLAIN_LINE)
    assert msg is not None
    assert msg.nick == "Flomaster"
    assert msg.text == "А ангир будут исправлять?"


def test_strips_line_ending():
    msg = parse_line(PLAIN_LINE + "\r\n")
    assert msg is not None
    assert msg.raw == PLAIN_LINE


def test_ignores_system_line():
    assert parse_line(SYSTEM_LINE) is None


def test_ignores_other_channel():
    assert parse_line(OTHER_CHANNEL_LINE) is None


def test_ignores_garbage():
    assert parse_line("") is None
    assert parse_line("[3.Поиск группы] без даты") is None


def test_clean_text():
    assert clean_text("  [cmd:X;abc=]Хил [item:1;ver2;;;] ") == "Хил [item]"
