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
    assert msg.text == "wts [Предмет 168000066][Предмет 168000067] вставка"


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
    assert clean_text("  [cmd:X;abc=]Хил [item:1;ver2;;;] ") == "Хил [Предмет 1]"


def test_collects_item_ids_in_order():
    msg = parse_line(ITEM_LINE)
    assert msg is not None
    assert msg.item_ids == ("168000066", "168000067")


def test_no_item_ids_for_plain_message():
    msg = parse_line(PLAIN_LINE)
    assert msg is not None
    assert msg.item_ids == ()


def test_known_item_links_show_names():
    names = {"168000066": "Клинок Рудры"}
    msg = parse_line(ITEM_LINE, names)
    assert msg is not None
    assert msg.text == "wts [Клинок Рудры][Предмет 168000067] вставка"
    assert msg.item_ids == ("168000066", "168000067")


def test_clean_text_with_names():
    assert clean_text("[item:1;ver2;;;] и [item:2;ver2;;;]", {"2": "Меч Фланаса"}) == "[Предмет 1] и [Меч Фланаса]"


# --- any channel (for «Весь чат») -------------------------------------------------
from watcher.parser import parse_any_line  # noqa: E402


def test_any_line_player_in_channel():
    line = parse_any_line(CMD_LINE)
    assert (line.channel, line.nick, line.text) == ("3.Поиск группы", "Tiyamate", "WTB MMK 2.2KK SM++++++++++++++")
    assert line.time == "2026.10.08 18:43:17"
    assert line.is_player


def test_any_line_system_message():
    line = parse_any_line(SYSTEM_LINE)
    assert (line.channel, line.nick, line.is_player) == (None, None, False)
    assert line.text == "Бешеный ветер I: Скор. движ. цели Mockoco увеличивается."


def test_any_line_bracket_system_channel():
    line = parse_any_line("2026.10.08 16:00:00 : [Event] PvP Team Arena 1x1 registration is open! ")
    assert (line.channel, line.nick, line.is_player) == ("Event", None, False)
    assert line.text == "PvP Team Arena 1x1 registration is open!"


def test_any_line_player_without_channel_and_whisper_verb():
    line = parse_any_line("2026.10.08 14:49:06 : [charname:Flama;0.0196 0.7843 0.8431]: 2 глада, чант? ")
    assert (line.channel, line.nick, line.text) == (None, "Flama", "2 глада, чант?")
    line = parse_any_line("2026.10.08 00:19:59 : [charname:Pyro;0.6275 1.0000 0.6275] шепчет: DP S? ")
    assert (line.nick, line.text) == ("Pyro", "DP S?")


def test_any_line_channel_with_plain_nick():
    line = parse_any_line("2026.10.08 14:50:49 : [3.Поиск группы] Sexbomb: [cmd:S;KU9=]ищу +1 SUP ")
    assert (line.channel, line.nick, line.text) == ("3.Поиск группы", "Sexbomb", "ищу +1 SUP")


def test_any_line_names_items_and_rejects_garbage():
    line = parse_any_line(
        "2026.10.08 14:40:27 : [charname:Dobrota;1 1 1]: [item:101700722;ver2;xx] за 5кк",
        {"101700722": "Длинный лук Рудры"},
    )
    assert line.text == "[Длинный лук Рудры] за 5кк"
    assert line.item_ids == ("101700722",)
    assert parse_any_line("[where:https://discord.gg/x]") is None


def test_search_also_catches_garbled_lfg_channel_and_plain_nick_format():
    garbled = "2026.10.08 00:18:15 : [3.????? ??????] [charname:Pyromancer;1 1 1]: [cmd:P;j=]DP S pls"
    msg = parse_line(garbled)
    assert msg is not None and (msg.nick, msg.text) == ("Pyromancer", "DP S pls")
    plain = "2026.10.08 14:50:49 : [3.Поиск группы] Sexbomb: ищу SUP"
    assert parse_line(plain).nick == "Sexbomb"
    assert parse_line("2026.10.08 14:49:06 : [charname:Flama;0 0 0]: whisper") is None


def test_any_line_keeps_name_color_and_verb():
    line = parse_any_line("2026.10.08 00:19:59 : [charname:Pyro;0.6275 1.0000 0.6275] шепчет: DP S? ")
    assert (line.color, line.verb) == ("0.6275 1.0000 0.6275", "шепчет")
    line = parse_any_line(CMD_LINE)
    assert (line.color, line.verb) == ("1.0000 0.6941 0.6941", "")
    assert parse_any_line(SYSTEM_LINE).color is None


def test_clean_text_place_quest_where_recipe_and_smileys():
    from watcher.parser import clean_text

    names = {"155007142": "Рецепт: клик", "186000163": "Монета"}
    text = (
        "[cmd:x;y]??? Форт [pos:Место;220070000 2010.1 1315.8 0.0 0] [pos:Место;999 1 2 0 0] "
        "кв [quest:2058] лег [where:sweet bunny] [recipe:155007142;0] [item_ex:186000163;Tw] го? ??"
    )
    from watcher.parser import display_text

    assert display_text(clean_text(text, names)) == (
        "Форт <Место · Келькмарос> <Место> кв <Задание: Уничтожение повстанцев Ривара> лег <sweet bunny> "
        "[Рецепт: клик] [Монета] го? ??"
    )


def test_pos_link_at_line_start_is_not_a_channel():
    from watcher.parser import parse_any_line

    line = parse_any_line("2026.10.09 14:52:29 : [pos:Место;220070000 1 2 0 0] тут")
    assert line.channel is None and line.text == "⟪Место · Келькмарос¦220070000 1 2⟫ тут"


def test_message_cut_inside_a_link():
    from watcher.parser import clean_text

    text = "[where:Вступай в легион][where:Окунись в PVE!!!] [where:Любой лвл!!!Г "
    assert clean_text(text) == "⟪Вступай в легион⟫⟪Окунись в PVE!!!⟫ ⟪Любой лвл!!!Г…⟫"
    assert clean_text("wts [item:100000893;ver2") == "wts …"


def test_unknown_quest_keeps_number():
    from watcher.parser import clean_text

    assert clean_text("кв [quest:99999999]") == "кв ⟪Задание 99999999⟫"


def test_place_link_keeps_coordinates():
    from watcher.parser import clean_text, split_place

    text = clean_text("[pos:Место;220070000 2010.1 1315.8 0.0 0] [pos:Босс;0 210050000 978.8 1265.0 0.0 0]")
    links = [part.split("⟫")[0] for part in text.split("⟪")[1:]]
    assert split_place(links[0]) == ("Место · Келькмарос", ("220070000", 2010.1, 1315.8))
    assert split_place(links[1]) == ("Босс · Ингисон", ("210050000", 978.8, 1265.0))
    assert split_place("sweet bunny") == ("sweet bunny", None)
