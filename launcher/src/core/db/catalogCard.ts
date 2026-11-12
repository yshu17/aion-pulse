/**
 * What the «База данных» card shows beside an item, and the cards of the other sections (pulse.db, schema 5).
 *
 *   itemSources(all, itemId) -> { drops, dropTotal, recipes, usedIn, vendors }   where an item comes from
 *   itemSkill(all, itemId) -> ItemSkill | null     the skill a skill book teaches or a stigma gives
 *   entityCard(all, entity, id) -> Row | null      a title, a pet, a quest or a recipe as a card
 *   linkParts(text, links) -> (string | GuideLink)[]   a guide's line cut at the names it links (an NPC, an item, a zone)
 */

import { recipesFor, type Recipe } from "./game";
import type { All } from "./npcPoints";
import { unpackIds } from "./packed";

type Row = Record<string, any>;

export interface NpcRef { id: string; name: string }
export interface ItemSources {
  drops: NpcRef[];      // the first NPCs that drop it, by name (not the technical records)
  dropTotal: number;    // how many NPCs drop it
  recipes: Recipe[];    // the recipes that make it
  usedIn: number;       // how many recipes need it
  vendors: (NpcRef & { kind: string })[];
}

const DROPS_SHOWN = 8;

export async function itemSources(all: All, itemId: number): Promise<ItemSources> {
  const [[item], used, sold, recipes] = await Promise.all([
    all("SELECT dropped_by FROM item WHERE id = ?", [itemId]),
    all("SELECT count(DISTINCT recipe_id) AS n FROM recipe_part WHERE item_id = ?", [itemId]),
    all("SELECT v.npc_id, v.kind, coalesce(n.name, '') AS name FROM vendor_item v LEFT JOIN npc n ON n.id = v.npc_id "
      + "WHERE v.item_id = ? ORDER BY n.name, v.npc_id", [itemId]),
    recipesFor(all, String(itemId)),
  ]);
  const ids = unpackIds(item?.dropped_by, true);
  const named = ids.length
    ? await all("SELECT id, name FROM npc WHERE id IN (SELECT CAST(value AS TEXT) FROM json_each(?)) AND name <> '' "
      + "AND service = 0 AND instr(name, '_') = 0 ORDER BY name LIMIT ?", // technical records («DF4_ЕжедневныйКвест_…») stay out
      [JSON.stringify(ids), DROPS_SHOWN])
    : [];
  return {
    drops: named.map((r) => ({ id: String(r.id), name: String(r.name) })),
    dropTotal: ids.length,
    recipes,
    usedIn: Number(used[0]?.n ?? 0),
    vendors: sold.map((r) => ({ id: String(r.npc_id), name: String(r.name || r.npc_id), kind: String(r.kind) })),
  };
}

export interface ItemSkill { kind: "book" | "stigma"; name: string; description: string; damage: string | null; icon: string; level: number | null; classes: Record<string, number> }

export async function itemSkill(all: All, itemId: number): Promise<ItemSkill | null> {
  const [book] = await all(
    "SELECT b.skill, b.classes, s.name, s.description, s.icon, d.text AS damage FROM skill_book b LEFT JOIN skill s ON s.id = b.skill_id LEFT JOIN skill_damage d ON d.skill_id = b.skill_id WHERE b.item_id = ?", [itemId]);
  if (book) {
    return { kind: "book", name: book.name || book.skill || "", description: book.description ?? "", damage: book.damage ?? null, icon: book.icon ?? "", level: null,
      classes: book.classes ? JSON.parse(book.classes) : {} };
  }
  const [stigma] = await all(
    "SELECT g.skill, g.gain_level, s.name, s.description, s.icon, d.text AS damage FROM stigma g LEFT JOIN skill s ON s.id = g.skill_id LEFT JOIN skill_damage d ON d.skill_id = g.skill_id WHERE g.item_id = ?", [itemId]);
  if (!stigma || !(stigma.name || stigma.skill)) return null;
  return { kind: "stigma", name: stigma.name || stigma.skill, description: stigma.description ?? "", damage: stigma.damage ?? null, icon: stigma.icon ?? "",
    level: stigma.gain_level ?? null, classes: {} };
}

export async function entityCard(all: All, entity: string, id: number): Promise<Row | null> {
  const table = { title: "title", pet: "pet", quest: "quest", recipe: "recipe" }[entity];
  if (!table) return null;
  const [row] = await all(`SELECT * FROM ${table} WHERE id = ?`, [id]);
  return row ?? null;
}

export interface QuestNpc { id: string; name: string; zone: string; map_id: string; at: [number, number] | null }
export interface QuestStep {
  do: "kill" | "loot" | "gather" | "buy" | "drop" | "craft" | "after";
  item?: { id: string; name: string; grade: string; icon: string } | null;
  count?: number | null;
  from?: { id: string; name: string }[];
  more?: number;
  skill?: string;
  level?: number | null;
  quests?: { id: string; name: string }[];
}
/** The guide of a quest from aidb.ru (quest_guide): what the client's tables do not hold. */
/** A name inside a guide's line and what it is: «npcs» (an NPC or a monster), «items», «zones» (a map_id). */
export interface GuideLink { kind: "npcs" | "items" | "zones"; id: string; name: string }
export interface QuestGuide {
  name_en: string; category: string; race: string; classes: string[]; level: number | null; rec_level: number | null; repeat: string; notes: string[];
  zone: string; zoneId: string; title: string; steps: { text: string; links: GuideLink[] }[]; needs: { id: string; name: string; count: number; grade: string; icon: string }[];
  choice: { id: string; name: string; count: number; grade: string; icon: string }[]; giverName: string; enderName: string;
}
export interface QuestCard {
  guide: QuestGuide | null;
  id: string; name: string; gold: boolean; kind: string; zone: string; min_level: number | null; max_level: number | null;
  races: string[]; repeatable: boolean; giver: QuestNpc | null; ender: QuestNpc | null; steps: QuestStep[];
  rewards: { type: string; amount: number; choice: boolean; item: { id: string; name: string; grade: string; icon: string } | null }[];
}

/** A guide's line cut into plain text and the names it links, in the order of the text (the longest name first where two overlap). */
export function linkParts(text: string, links: GuideLink[]): (string | GuideLink)[] {
  const found: { at: number; link: GuideLink }[] = [];
  for (const link of [...links].sort((a, b) => b.name.length - a.name.length)) {
    if (!link.name) continue;
    for (let at = text.indexOf(link.name); at >= 0; at = text.indexOf(link.name, at + link.name.length)) {
      if (!found.some((f) => at < f.at + f.link.name.length && f.at < at + link.name.length)) found.push({ at, link });
    }
  }
  found.sort((a, b) => a.at - b.at);
  const parts: (string | GuideLink)[] = [];
  let from = 0;
  for (const { at, link } of found) {
    if (at > from) parts.push(text.slice(from, at));
    parts.push(link);
    from = at + link.name.length;
  }
  if (from < text.length) parts.push(text.slice(from));
  return parts;
}

/** The quest's kind and region from its category («mission | Фоэта»): a mission (the campaign) wears the gold icon. */
export function questKind(category: string | null | undefined): { kind: string; zone: string; gold: boolean } {
  const [kind = "", zone = ""] = String(category ?? "").split("|").map((s) => s.trim());
  return { kind, zone, gold: kind === "mission" };
}

async function questNpc(all: All, id: string | null): Promise<QuestNpc | null> {
  if (!id) return null;
  const [[npc], [zone], [point]] = await Promise.all([
    all("SELECT id, name FROM npc WHERE id = ?", [id]),
    all("SELECT name, map_id FROM npc_zone WHERE npc_id = ? LIMIT 1", [id]),
    all("SELECT map_id, x, y FROM npc_point WHERE npc_id = ? ORDER BY source = 'map' DESC LIMIT 1", [id]),
  ]);
  if (!npc) return { id, name: `NPC ${id}`, zone: "", map_id: "", at: null };
  return { id, name: String(npc.name || `NPC ${id}`), zone: String(zone?.name ?? ""), map_id: String(point?.map_id ?? zone?.map_id ?? ""),
    at: point ? [Number(point.x), Number(point.y)] : null };
}

export async function questCard(all: All, id: number): Promise<QuestCard | null> {
  const [q] = await all("SELECT * FROM quest WHERE id = ?", [id]);
  if (!q) return null;
  const steps: Row[] = q.steps ? JSON.parse(q.steps) : [];
  const rewards: Row[] = q.rewards ? JSON.parse(q.rewards) : [];
  const itemIds = [...steps.map((s) => s.item), ...rewards.map((r) => r.item)].filter((v) => v !== null && v !== undefined).map(Number);
  const questIds = steps.flatMap((s) => s.quests ?? []).map(Number);
  const [guideRow] = await all("SELECT * FROM quest_guide WHERE quest_id = ?", [id]).catch(() => []); // an older database has no guide table
  const guideItems: Row[] = guideRow ? [...JSON.parse(guideRow.needs ?? "[]"), ...(JSON.parse(guideRow.rewards ?? "{}").choice ?? [])] : [];
  itemIds.push(...guideItems.map((i) => Number(i.id)));
  const [items, quests, giver, ender] = await Promise.all([
    itemIds.length ? all("SELECT id, name, grade, icon FROM item WHERE id IN (SELECT value FROM json_each(?))", [JSON.stringify(itemIds)]) : [],
    questIds.length ? all("SELECT id, name FROM quest WHERE id IN (SELECT value FROM json_each(?))", [JSON.stringify(questIds)]) : [],
    questNpc(all, q.giver), q.ender && q.ender !== q.giver ? questNpc(all, q.ender) : Promise.resolve(null),
  ]);
  const item = (v: unknown) => {
    const row = items.find((r) => Number(r.id) === Number(v));
    return v === null || v === undefined ? null : { id: String(v), name: String(row?.name ?? `ID ${v}`), grade: String(row?.grade ?? ""), icon: String(row?.icon ?? "") };
  };
  const { kind, zone, gold: missionByCategory } = questKind(q.category);
  const gold = guideRow ? guideRow.icon === "mission" : missionByCategory;
  const withItem = (i: Row) => ({ id: String(i.id), name: String(i.name), count: Number(i.count ?? 1), grade: String(items.find((r) => Number(r.id) === Number(i.id))?.grade ?? ""),
    icon: String(items.find((r) => Number(r.id) === Number(i.id))?.icon ?? "") });
  const guide: QuestGuide | null = guideRow ? {
    name_en: String(guideRow.name_en ?? ""), category: String(guideRow.category ?? ""), race: String(guideRow.race ?? ""),
    classes: JSON.parse(guideRow.classes ?? "[]"), level: guideRow.level ?? null, rec_level: guideRow.rec_level ?? null, repeat: String(guideRow.repeat ?? ""),
    notes: JSON.parse(guideRow.notes ?? "[]"), zone: String(guideRow.zone_name ?? ""), zoneId: String(guideRow.zone_id ?? ""), title: String(guideRow.title ?? ""),
    steps: JSON.parse(guideRow.steps ?? "[]").map((st: Row) => ({ text: String(st.text),
      links: (st.links ?? []).map((l: Row): GuideLink => ({ kind: l.kind, id: String(l.id), name: String(l.name ?? "") })) })),
    needs: JSON.parse(guideRow.needs ?? "[]").map(withItem), choice: (JSON.parse(guideRow.rewards ?? "{}").choice ?? []).map(withItem),
    giverName: String(guideRow.giver_name ?? ""), enderName: String(guideRow.ender_name ?? ""),
  } : null;
  return {
    guide,
    id: String(q.id), name: String(q.name), gold, kind, zone, min_level: q.min_level, max_level: q.max_level,
    races: q.race ? String(q.race).split(",") : [], repeatable: Boolean(q.repeatable), giver, ender,
    steps: steps.map((s): QuestStep => ({
      do: s.do, item: s.item === undefined ? undefined : item(s.item), count: s.count ?? null,
      from: (s.from ?? []).map(([nid, name]: [string, string]) => ({ id: String(nid), name })), more: s.more ?? 0,
      skill: s.skill, level: s.level ?? null,
      quests: (s.quests ?? []).map((qid: number) => ({ id: String(qid), name: String(quests.find((r) => Number(r.id) === qid)?.name ?? `ID ${qid}`) })),
    })),
    rewards: rewards.map((r) => ({ type: String(r.type), amount: Number(r.amount ?? 0), choice: String(r.group ?? "").startsWith("selectable"),
      item: r.item ? item(r.item) : null })),
  };
}
