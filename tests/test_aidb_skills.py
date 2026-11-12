"""The skill damage read from aidb.ru skill pages (core/pulse_db/aidb_skills.py)."""

from core.pulse_db.aidb_skills import parse_page

PAGE = (
    '<section class="card" id="descr">\n  <h2 class="card-title">Описание</h2>\n'
    '  <div class="rich">Физическая атака, наносит цели 661-665 ед. урона.</div>\n</section>'
)


def test_range_damage():
    got = parse_page(PAGE)
    assert got == {"text": "Физическая атака, наносит цели 661-665 ед. урона.", "min": 661, "max": 665}


def test_single_number_damage():
    got = parse_page(PAGE.replace("661-665", "120"))
    assert (got["min"], got["max"]) == (120, 120)


def test_no_damage_keeps_text():
    got = parse_page(PAGE.replace("Физическая атака, наносит цели 661-665 ед. урона.", "Увеличивает радиус действия умений на 25%."))
    assert got["min"] is None and got["max"] is None
    assert got["text"] == "Увеличивает радиус действия умений на 25%."


def test_no_description_block():
    assert parse_page("<html><body>nothing</body></html>") is None
