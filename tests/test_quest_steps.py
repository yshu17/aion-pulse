"""core/pulse_db/quest_steps.py: a quest's steps from the client's quest tables, nothing guessed."""

from core.pulse_db.quest_steps import quest_steps


def test_steps_from_kills_drops_gathering_crafting_and_earlier_quests(tmp_path):
    (tmp_path / "quest_script_monster.csv").write_text(
        "questId,progress,item,sourceType,sourceName,num,monsters_gathers_npcs_list\n"
        "1001,Progress(2),,killedByUser,,3,WCherubimL_3_n,Unknown_Mob\n"
        "1001,Progress(2),,killedByUser,,3,WCherubimL_3_n,Unknown_Mob\n", encoding="utf-8")  # the same step twice: once
    (tmp_path / "quest_monster.csv").write_text(
        "questId, questProgress, item, sourceType, sourceName, num, monsters_gathers_npcs_list\n"
        "1001,1,quest_1001A,questItemDropMonster,,1,wcherubiml_4_n\n"
        "1001,2,quest_1001a,questItemDropMonster,,1,wcherubiml_3_n\n"   # the same item from more monsters: one step
        "1001,3,quest_1001b,simpleQuest,,1,\n"          # the quest gives it: no step
        "1002,1,herb_a,gatherSource,herb,2,gather_herb\n"
        "short,row\n", encoding="utf-8")
    npcs = {"wcherubiml_3_n": ("700001", "Керубим"), "wcherubiml_4_n": ("700002", "Злой керубим")}
    items = {"quest_1001a": 182200001, "herb_a": 152000001}
    fields = {1001: {"name": "Q1001", "collect_item1": "quest_1001a 5"}, 1003: {"name": "Q1003", "combineskill": "alchemy", "combine_skillpoint": "100",
                                              "finished_quest_cond1": "Q1001"}}
    steps = quest_steps(tmp_path, fields, npcs, items, {"Q1001": 1001, "Q1003": 1003})
    assert steps[1001] == [
        {"do": "loot", "item": 182200001, "count": 5, "from": [["700002", "Злой керубим"], ["700001", "Керубим"]], "more": 0},  # progress 1 first
        {"do": "kill", "from": [["700001", "Керубим"]], "more": 1},  # one mob pulse.db does not know: counted
    ]
    assert steps[1002] == [{"do": "gather", "item": 152000001, "count": None, "from": [], "more": 1}]  # no wanted count known
    assert steps[1003] == [{"do": "after", "quests": [1001]}, {"do": "craft", "skill": "alchemy", "level": 100}]


def test_no_tables_give_only_the_quest_fields(tmp_path):
    assert quest_steps(None, {5: {"name": "Q5"}}, {}, {}, {}) == {}
