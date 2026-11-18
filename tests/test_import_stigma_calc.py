"""tools/import_stigma_calc.py reads the stigma calculator's class files as text: the trees and the faction's choices."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("import_stigma_calc", Path(__file__).resolve().parent.parent / "tools" / "import_stigma_calc.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

CODE = '''
  getFirstStigmaTree(): AdvancedStigmaTreeSlots {
    return {
      tier1: "ra_lightningshot",
      tier2_1: "ra_shadowarrow",
      tier2_2:
        this.faction === "elyos"
          ? "ra_blazingtrap_light"
          : "ra_blazingtrap_dark",
      tier3_1: "ra_movingshot",
      tier3_2: "ra_panthermove",
      tier4_1: "ra_backdashstab",
      tier4_2: "ra_breathofnature",
      tier4_3: "ra_throwingtrap",
      tier4_4: "ra_breathofnature",
      tier4_5: "ra_throwingtrap",
    };
  }
'''


def test_tree_in_drawing_order_for_each_faction():
    for group, trap in ((1, "ra_blazingtrap_light"), (2, "ra_blazingtrap_dark")):
        text = mod.TERNARY.sub(lambda m, g=group: m.group(g), CODE)
        assert mod.tree(text, "getFirstStigmaTree") == [
            "ra_backdashstab", "ra_breathofnature", "ra_throwingtrap", "ra_movingshot", "ra_panthermove",
            "ra_breathofnature", "ra_throwingtrap", "ra_shadowarrow", trap, "ra_lightningshot"]


def test_level_keeps_costs_and_times():
    row = {"45": {"id": 411, "name": "Divine Justice I", "Usage Cost": "165 MP", "Cast time": "0.5 sec", "Cooldown": "120",
                  "Description": "Inflicts 760 earth damage", "Abyss point": 13750, "Shards cost": 225}}
    assert mod.level(row, 45) == {"level": 45, "skill": 411, "name": "Divine Justice I", "text": "Inflicts 760 earth damage", "mp": "165 MP",
                                  "cast": "0.5 sec", "cooldown": "120", "shards": 225, "ap": 13750}
