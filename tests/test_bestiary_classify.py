from watcher.bestiary_classify import plan, stem_key, technical_name


def _row(npc_id, name, points=0, level="55", category="monster", drops=0, profile=1, sig=None):
    return {"id": npc_id, "name": name, "level": level, "category": category, "points": points, "drops": drops,
            "profile": profile, "sig": sig or (f"p{points}", "", "")}


def test_technical_names():
    for name in ("Test_главный монстр 1", "BAb1_Страж_Асмодианин_lv50", "Guard", "NPC123", "123", "", "a_b"):
        assert technical_name(name), name
    for name in ("Хранитель Валон", "Драконид-страж 47-го легиона", "Стражник-воитель", "Торговец 100%"):
        assert not technical_name(name), name


def test_stem_key_ignores_case_endings_and_order():
    assert stem_key("хранителя Валона") == stem_key("Хранитель Валон") == stem_key("Валон хранитель")


def test_new_stats_variant_takes_points_and_duplicates_are_service():
    rows = [
        _row("1", "Хранитель Валон", points=5, drops=100),
        _row("2", "Новые характеристики хранителя Валона"),
        _row("3", "Хранитель Валон", sig=("p5", "", "")),  # same name, level and content: a duplicate
        _row("7", "Торговец", level="20", sig=("p0", "stockA", "")), _row("8", "Торговец", level="20", sig=("p0", "stockB", "")),
        _row("9", "Мудрец", points=2, sig=("here", "", "")), _row("10", "Мудрец", points=2, sig=("there", "", "")),
        _row("4", "Кабан", level="5", points=3), _row("5", "Кабан", level="6", points=3),  # other level: kept
        _row("6", "Test_x"),
    ]
    donors, service = plan(rows)
    assert donors["2"] == "1"
    assert service == {"3", "6"}  # other wares or other places are not duplicates


def test_plural_forms():
    from watcher.bestiary_labels import plural
    assert [plural(n, "точка", "точки", "точек") for n in (1, 2, 5, 11, 21, 112)] == [
        "1 точка", "2 точки", "5 точек", "11 точек", "21 точка", "112 точек"]
