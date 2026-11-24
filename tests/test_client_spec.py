"""core/pulse_db/client_spec.py: an item's card (spec) made from the game client's own record, for the items the old crawl never had."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.pulse_db.client_spec import client_spec, has_glitch, repaired_spec, resolve_text, stat_text  # noqa: E402

FOOD_SKILL = {
    "name": "food_hpregen_mpregen", "type": "Magical",
    "effect1_type": "StatUp", "effect1_effectid": "10013", "effect1_reserved1": "2", "effect1_reserved13": "hpRegen", "effect1_remain2": "1800000",
    "effect2_type": "StatUp", "effect2_effectid": "10013", "effect2_reserved1": "3", "effect2_reserved13": "mpRegen", "effect2_remain2": "1800000",
}
FOOD_TEMPLATE = "[%e1.StatUp.StatName]% +[%e1.StatUp.Value]. [%e2.StatUp.StatName]% +[%e2.StatUp.Value]. Время действия: [%e1.StatUp.RemainTime]"
FLAGS_ALL_FALSE = {"can_exchange": "FALSE", "can_sell_to_npc": "FALSE", "can_deposit_to_account_warehouse": "FALSE",
                   "can_deposit_to_character_warehouse": "FALSE", "can_deposit_to_guild_warehouse": "FALSE"}


def stat_up(key: str, value: str, ms: int = 600000, index: int = 1) -> dict:
    return {f"effect{index}_type": "StatUp", f"effect{index}_reserved13": key, f"effect{index}_reserved1": value, f"effect{index}_remain2": str(ms)}


def test_a_stat_is_named_the_way_the_game_names_it_and_a_percent_stat_gets_its_sign():
    assert stat_text("hpRegen", "2") == "Восст. HP +2"
    assert stat_text("Maxhp", "40") == "Макс. HP +40"
    assert stat_text("MagicalResist", "5") == "Маг. защита +5"
    assert stat_text("ElementalDefendFire", "20") == "Защ. от огня +20"
    assert stat_text("Speed", "10") == "Скорость +10%"
    assert stat_text("Attackdelay", "3") == "Скорость атаки +3%"


def test_a_stat_the_game_names_do_not_cover_is_not_shown_raw():
    assert stat_text("allresist", "10") is None
    assert stat_text("hpRegen", "") is None


def test_the_placeholders_of_a_food_description_are_filled_from_the_skill():
    text, complete = resolve_text(FOOD_TEMPLATE, {"effects": FOOD_SKILL})
    assert complete
    assert text == "Восст. HP +2. Восст. MP +3. Время действия: 30 мин."


def test_a_scroll_without_the_percent_mark_in_its_template_reads_the_same():
    text, complete = resolve_text("[%e1.StatUp.StatName] +[%e1.StatUp.Value]. Время действия: [%e1.StatUp.RemainTime]",
                                  {"effects": stat_up("PhysicalDefend", "10")})
    assert (text, complete) == ("Физ. защита +10. Время действия: 10 мин.", True)


def test_a_percent_stat_with_the_clients_escaped_percent_signs():
    text, complete = resolve_text("Значок. [%e1.StatUp.StatName]% +[%e1.StatUp.Value]%%. Время действия: [%e1.StatUp.RemainTime]",
                                  {"effects": stat_up("Speed", "10", 300000)})
    assert (text, complete) == ("Значок. Скорость +10%. Время действия: 5 мин.", True)


def test_a_duration_reads_in_seconds_minutes_or_hours():
    template = "Время действия: [%e1.StatUp.RemainTime]"
    assert resolve_text(template, {"effects": stat_up("maxhp", "1", 20000)})[0] == "Время действия: 20 сек."
    assert resolve_text(template, {"effects": stat_up("maxhp", "1", 300000)})[0] == "Время действия: 5 мин."
    assert resolve_text(template, {"effects": stat_up("maxhp", "1", 3600000)})[0] == "Время действия: 1 ч."
    assert resolve_text(template, {"effects": stat_up("maxhp", "1", 5400000)})[0] == "Время действия: 90 мин."


def test_a_heal_over_time_reads_the_points_the_interval_and_the_time():
    potion = {"effect2_type": "Heal", "effect2_checktime": "2000", "effect2_reserved9": "154", "effect2_remain2": "20000"}
    template = "Восстанавливает по [%e2.Heal.CheckTimeHeal] HP с интервалом в [%e2.Heal.CheckTime] Время действия: [%e2.Heal.RemainTime]"
    assert resolve_text(template, {"effects": potion}) == ("Восстанавливает по 154 HP с интервалом в 2 сек. Время действия: 20 сек.", True)
    mana = {"effect2_type": "MpHeal", "effect2_checktime": "2000", "effect2_reserved9": "160", "effect2_remain2": "20000"}
    assert resolve_text("Восстанавливает по [%e2.MPHeal.CheckTimeHeal] MP", {"effects": mana}) == ("Восстанавливает по 160 MP", True)


def test_an_instant_heal_and_a_shield_read_their_numbers():
    pie = {"effect1_type": "ProcHeal_Instant", "effect1_reserved2": "5000", "effect2_type": "ProcMpHeal_Instant", "effect2_reserved2": "4000"}
    text, _ = resolve_text("Восстанавливает [%e1.ProcHeal_Instant.Heal] HP и [%e2.ProcMpHeal_Instant.Heal] MP.", {"effects": pie})
    assert text == "Восстанавливает 5000 HP и 4000 MP."
    amulet = {"effect1_type": "Shield", "effect1_reserved2": "421", "effect1_remain2": "24000"}
    text, _ = resolve_text("Поглощает до [%e1.Shield.CoverValue] ед. урона от каждой физической атаки. Время действия: [%e1.Shield.RemainTime]", {"effects": amulet})
    assert text == "Поглощает до 421 ед. урона от каждой физической атаки. Время действия: 24 сек."


def test_a_percent_sign_the_client_escapes_is_one_percent_sign():
    assert resolve_text("Скорость +10%%.", {"effects": {}}) == ("Скорость +10%.", True)


def test_a_sentence_we_cannot_fill_is_left_out_whole_and_an_abbreviation_does_not_cut_it():
    candy = {"effect2_type": "StatUp", "effect2_reserved13": "phyAttack", "effect2_reserved1": "0", "effect2_remain2": "3600000"}
    text, complete = resolve_text("Превращают в Дуэлянта на 60 минут. [%e2.StatUp.StatName]% +[%e2.StatUp.Value].", {"effects": candy})
    assert (text, complete) == ("Превращают в Дуэлянта на 60 минут.", False)
    amulet = {"effect1_type": "Shield", "effect1_reserved2": "0"}
    text, complete = resolve_text("Амулет. Поглощает до [%e1.Shield.CoverValue] ед. урона от атаки. Конец.", {"effects": amulet})
    assert (text, complete) == ("Амулет. Конец.", False)  # «ед. урона» is not cut in two


def test_a_plain_description_is_taken_as_it_is_with_its_line_breaks():
    spec = client_spec(name="Модель меча", grade="common", description="Это модель.\\nДля изготовления меча.", fields=FLAGS_ALL_FALSE, skill=None)
    texts = [b["text"] for b in spec["blocks"] if b["kind"] == "text"]
    assert texts == ["Это модель. Для изготовления меча."]


def test_the_trade_flags_of_the_client_become_the_cards_lines_in_the_games_order():
    spec = client_spec(name="Ящик", grade="common", description="Внутри предмет.", fields=FLAGS_ALL_FALSE, skill=None)
    props = [b for b in spec["blocks"] if b["kind"] == "props"][0]["lines"]
    assert props == ["[Нельзя обменять]", "[Нельзя продать торговцу]", "[Нельзя положить на склад аккаунта]",
                     "[Нельзя положить на склад]", "[Нельзя положить на склад легиона]"]
    free = {key: "TRUE" for key in FLAGS_ALL_FALSE}
    assert not [b for b in client_spec(name="Ящик", grade="common", description="x", fields=free, skill=None)["blocks"] if b["kind"] == "props"]


def test_the_spec_has_the_shape_the_old_ones_have_and_is_plain_json():
    spec = client_spec(name="Бешевый коктейль", grade="rare", description=FOOD_TEMPLATE, fields=FLAGS_ALL_FALSE, skill={"effects": FOOD_SKILL, "name": "Повышение скорости восстановления HP/MP"})
    assert spec["name"] == "Бешевый коктейль" and spec["grade"] == "rare"
    assert [b["kind"] for b in spec["blocks"]] == ["props", "hr", "text"]
    assert spec["blocks"][2] == {"kind": "text", "text": "Восст. HP +2. Восст. MP +3. Время действия: 30 мин.", "style": "normal"}
    json.dumps(spec, ensure_ascii=False)


def test_a_description_that_cannot_be_read_at_all_falls_back_to_the_skills_name():
    candy = {"effect2_type": "StatUp", "effect2_reserved13": "phyAttack", "effect2_reserved1": "0"}
    spec = client_spec(name="Леденец", grade="common", description="[%e2.StatUp.StatName]% +[%e2.StatUp.Value].", fields={}, skill={"effects": candy, "name": "Усиление атаки"})
    assert [b["text"] for b in spec["blocks"] if b["kind"] == "text"] == ["Эффект: Усиление атаки."]
    assert client_spec(name="Леденец", grade="common", description="[%buyduration]", fields={}, skill=None) is None


def test_no_description_means_no_spec():
    assert client_spec(name="Тест", grade="common", description="  ", fields=FLAGS_ALL_FALSE, skill=None) is None
    assert client_spec(name="Тест", grade="common", description=None, fields={}, skill=None) is None


def test_a_crawl_text_the_site_left_half_filled_is_a_glitch_and_a_good_one_is_not():
    for bad in ("Макс. HP% +40. Макс. MP% +40. Время действия: 30 мин.", "hpRegen% +2. mpRegen% +3.", "ElementalDefendAll% +10.",
                "allresist +0. Время действия: 10 мин.", "[%e1.StatUp.StatName]% +[%e1.StatUp.Value]."):
        assert has_glitch(bad), bad
    for good in ("Макс. HP +40. Время действия: 30 мин.", "Скорость +10%. Время действия: 5 мин.", "Физ. защита +10. Время действия: 10 мин.", ""):
        assert not has_glitch(good), good


def test_a_glitchy_text_block_is_replaced_and_the_rest_of_the_card_stays():
    card = {"name": "Шкура древня", "grade": "common", "blocks": [
        {"kind": "pairs", "rows": [["Ранг", "[Обычный]"], ["Тип", "[Еда]"]]}, {"kind": "hr"},
        {"kind": "text", "text": "Макс. HP% +40. Макс. MP% +40. Время действия: 30 мин.", "style": "normal"}]}
    skill = {"effects": {**stat_up("maxhp", "40", 1800000), **stat_up("MaxMp", "40", 1800000, index=2)}}
    fixed = repaired_spec(card, "[%e1.StatUp.StatName]% +[%e1.StatUp.Value]. [%e2.StatUp.StatName]% +[%e2.StatUp.Value]. Время действия: [%e1.StatUp.RemainTime]", skill)
    assert fixed["blocks"][:2] == card["blocks"][:2]  # rank and type stay
    assert fixed["blocks"][2]["text"] == "Макс. HP +40. Макс. MP +40. Время действия: 30 мин."


def test_a_card_is_not_touched_when_it_is_fine_or_the_clients_text_cannot_be_filled():
    fine = {"blocks": [{"kind": "text", "text": "Макс. HP +40. Время действия: 30 мин.", "style": "normal"}]}
    assert repaired_spec(fine, "[%e1.StatUp.StatName] +[%e1.StatUp.Value].", {"effects": stat_up("maxhp", "40")}) is None
    glitchy = {"blocks": [{"kind": "text", "text": "allresist +0. Время действия: 10 мин.", "style": "normal"}]}
    assert repaired_spec(glitchy, "[%e1.StatUp.StatName] +[%e1.StatUp.Value].", {"effects": stat_up("allresist", "10")}) is None  # unknown key
    assert repaired_spec(glitchy, "", {"effects": {}}) is None
