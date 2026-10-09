import json
from pathlib import Path

from watcher.specs import load_specs, parse_spec

FIXTURE = Path(__file__).parent / "fixtures" / "item_110600968.html"


def spec():
    return parse_spec(FIXTURE.read_text(encoding="utf-8"))


def kinds(blocks):
    return [b["kind"] for b in blocks]


def test_header():
    s = spec()
    assert s["name"] == "Кираса Рудры"
    assert s["grade"] == "epic"


def test_block_order():
    assert kinds(spec()["blocks"]) == [
        "pairs",  # Ранг, Тип
        "props",
        "warning",
        "hr",
        "grid",  # Физ. защита ...
        "text",  # Надев все предметы комплекта ...
        "hr",
        "grid",  # set bonus stats
        "hr",
        "grid",  # Усиление 0/15
        "hr",
        "text",  # Можно усилить магическими камнями ...
        "stones",
        "hr",
        "text",  # Латный комплект Рудры
        "set",
        "hr",
        "text",  # Эффект снаряжения (3)
        "grid",
        "text",  # Эффект снаряжения (5)
        "grid",
        "text",  # Эффект полного комплекта
        "grid",
    ]


def test_block_contents():
    b = spec()["blocks"]
    assert b[0]["rows"] == [["Ранг", "[Обычный]"], ["Тип", "Латная броня"]]
    assert b[1]["lines"] == [
        "[Нельзя обменять]",
        "[Нельзя положить на склад аккаунта]",
        "[Нельзя положить на склад легиона]",
    ]
    assert b[2]["text"] == "Можно использовать с 55-го уровня."
    assert b[4]["pairs"] == [["Физ. защита", "418"], ["Маг. сопр.", "127"], ["Уклонение", "209"]]
    assert b[4]["dim"] is False
    assert b[5] == {"kind": "text", "text": "Надев все предметы комплекта, вы получите дополнительный эффект.", "style": "normal"}
    assert b[7]["pairs"] == [
        ["Макс. HP", "+407"],
        ["Физ. защита", "+89"],
        ["Блок щитом", "+91"],
        ["Скор. полёта", "+10%"],
        ["Агрессия", "+67%"],
    ]
    assert b[9]["pairs"] == [["Усиление", "0/15"]]
    assert b[12] == {"kind": "stones", "count": 6, "bonus": 1}
    assert b[14] == {"kind": "text", "text": "Латный комплект Рудры", "style": "epic"}
    assert b[15]["items"] == [
        "Латные рукавицы Рудры",
        "Латные набедренники Рудры",
        "Латные сапоги Рудры",
        "Латные щитки Рудры",
        "Кираса Рудры",
    ]
    assert b[17] == {"kind": "text", "text": "Эффект снаряжения (3)", "style": "muted"}
    assert b[18] == {"kind": "grid", "pairs": [["Маг. защита", "+69"]], "dim": True}
    assert b[22]["pairs"] == [["Физ. атака", "+19"], ["Точность", "+74"]]


def test_load_specs(tmp_path):
    path = tmp_path / "item_specs.json"
    path.write_text(json.dumps({"1": {"name": "x", "grade": "epic", "blocks": []}}), encoding="utf-8")
    assert load_specs(path) == {"1": {"name": "x", "grade": "epic", "blocks": []}}
    assert load_specs(tmp_path / "missing.json") == {}


def test_load_specs_gzip_with_lazy_json_values(tmp_path):
    import gzip
    import json

    path = tmp_path / "item_specs.json.gz"
    spec = {"name": "x", "grade": "epic", "blocks": []}
    path.write_bytes(gzip.compress(json.dumps({"1": json.dumps(spec)}).encode("utf-8")))
    specs = load_specs(path)
    assert "1" in specs and "2" not in specs
    assert specs["1"] == spec
    assert specs.get("2") is None
    assert len(specs) == 1
