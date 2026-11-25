/**
 * The quests of an NPC for its card on the «NPC» tab (docs/TASKS_TG_2026-11-18.md, task 33). Reading only.
 *
 *   npcQuests(all, npcId) -> NpcQuest[]     the quests it gives (quest.giver) or takes back (quest.ender), by level
 *     takes  it takes the quest back and another NPC gives it; `giver` names that one («» when not known)
 *     zone   the part after «|» of the quest's category («quest | Арэшурат»), «» without one
 *   filterNpcQuests(list, "all" | "gives" | "takes", query) -> NpcQuest[]   by the role and a part of the name («ё» as «е»)
 */
import type { All } from "./npcPoints";

export interface NpcQuest { id: string; name: string; level: number; zone: string; repeat: boolean; gives: boolean; takes: boolean; giver: string }
export type QuestRole = "all" | "gives" | "takes";

export async function npcQuests(all: All, npcId: string): Promise<NpcQuest[]> {
  const rows = await all(
    "SELECT q.id, q.name, q.min_level, q.category, q.repeatable, q.giver, q.ender, "
      + "(SELECT name FROM npc WHERE id = q.giver) AS giver_name FROM quest q WHERE q.giver = ? OR q.ender = ? ORDER BY q.min_level, q.id",
    [npcId, npcId],
  );
  return rows.map((r) => {
    const gives = String(r.giver ?? "") === npcId;
    const takes = !gives && String(r.ender ?? "") === npcId;
    const category = String(r.category ?? "");
    return {
      id: String(r.id), name: String(r.name), level: Number(r.min_level ?? 0),
      zone: category.includes("|") ? category.slice(category.indexOf("|") + 1).trim() : "",
      repeat: Boolean(r.repeatable), gives, takes, giver: takes ? String(r.giver_name ?? "") : "",
    };
  });
}

const fold = (t: string) => t.toLowerCase().split("ё").join("е");

export function filterNpcQuests(list: NpcQuest[], role: QuestRole, query: string): NpcQuest[] {
  const q = fold(query.trim());
  return list.filter((x) => (role === "all" || (role === "gives" ? x.gives : x.takes)) && (!q || fold(x.name).includes(q)));
}
