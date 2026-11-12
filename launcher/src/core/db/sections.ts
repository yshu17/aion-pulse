/**
 * The ten sections of «База данных» (pulse.db tables db_section / db_section_entry, built by core/pulse_db/catalog.py).
 *
 *   sectionCounts(all) -> { "db:Предметы": n, ... }       the menu's sizes, one query
 *   sectionPage(all, "weapons", { query: "меч", sort: "level", offset: 0, limit: 50 })
 *     -> { total, rows: [{ id, name, kind, level, grade, icon }] }   a page of a section's list
 *
 * A database built before the sections (schema 4) still gives the six counts it can, from its own tables.
 */

import type { All } from "./npcPoints";

/** The item categories counted as armour (shields and headgear are their own kinds). */
const ARMOUR = ["Ткань", "Кожа", "Кольчуга", "Лата"];

export async function sectionCounts(all: All): Promise<Record<string, number>> {
  try {
    const rows = await all("SELECT title, count FROM db_section ORDER BY ord");
    if (rows.length) return Object.fromEntries(rows.map((r) => [`db:${r.title}`, Number(r.count)]));
  } catch {
    // an older database: no db_section table
  }
  const [row] = await all(
    `SELECT (SELECT count(*) FROM item) AS items,
            (SELECT count(*) FROM item WHERE category = 'Оружие') AS weapons,
            (SELECT count(*) FROM item WHERE category IN (SELECT value FROM json_each(?))) AS armour,
            (SELECT count(*) FROM item WHERE category = 'Украшения') AS jewels,
            (SELECT count(*) FROM quest) AS quests,
            (SELECT count(*) FROM recipe) AS recipes`,
    [JSON.stringify(ARMOUR)],
  );
  return {
    "db:Предметы": Number(row.items), "db:Оружие": Number(row.weapons), "db:Броня": Number(row.armour),
    "db:Украшения": Number(row.jewels), "db:Задания": Number(row.quests), "db:Рецепты": Number(row.recipes),
  };
}

export interface SectionRow {
  id: number;
  name: string;
  kind: string;   // the type: «Меч», «Лата», the quest's category, the recipe's profession …
  level: number | null;
  grade: string;  // an item's grade («epic»), "" for the rest
  icon: string;   // a picture of data/icons without «.png», "" when none
}

export interface PageOptions {
  query?: string;          // a part of the name (lower case, «ё» as «е») or the id
  grade?: string;          // only this grade («epic»)
  kind?: string;           // only this type («Меч»)
  levelMin?: number;       // the level from … to …, both included
  levelMax?: number;
  hideAbove?: number;      // hide the rows above this level; rows without a level (titles, pets …) stay
  slot?: string;           // armour: the gear slot («torso», «pants», «shoes», «shoulder», «glove») of gear_item
  cls?: string;            // skill books and stigmas: only this class' («fighter»), SKILL_CLASSES
  best?: boolean;          // skill books and stigmas: only the highest level of each skill («… III» without I and II)
  questType?: "gold" | "blue" | "darkblue" | "pink";  // a quest's mark: mission (gold), quest/task (blue), significant/important (dark blue), event (pink)
  race?: "light" | "dark" | "common";               // a quest's side: Элийцы, Асмодиане, both
  sort?: "name" | "level" | "id";
  desc?: boolean;
  offset?: number;
  limit?: number;
}

/** The section keys by the menu's title: «db:Оружие» opens «weapons». */
export const SECTION_KEY: Record<string, string> = {
  "Предметы": "items", "Оружие": "weapons", "Броня": "armour", "Украшения": "jewels", "Книги умений": "skill_books",
  "Стигмы": "stigmas", "Титулы": "titles", "Питомцы": "pets", "Задания": "quests", "Рецепты": "recipes",
};

/** Per entity: the table, its columns as a list row, and the expressions the filters and the sort use. */
interface Shape { table: string; join?: string; name: string; kind: string; level: string; grade: string; icon: string }
const SHAPE: Record<string, Shape> = {
  item: { table: "item", name: "t.name_key", kind: "coalesce(t.kind, t.category, '')", level: "t.level", grade: "coalesce(t.grade, '')", icon: "coalesce(t.icon, '')" },
  title: { table: "title", name: "t.name_key", kind: "''", level: "NULL", grade: "''", icon: "coalesce(t.icon, '')" },
  // a pet's type is what it does: a fighting one uses buffs («doping»), then the bag, the looting, the feeding
  pet: { table: "pet", name: "t.name_key", kind: "CASE WHEN t.functions LIKE '%doping%' THEN 'Боевой' WHEN t.functions LIKE '%warehouse%' THEN 'Склад' "
    + "WHEN t.functions LIKE '%looting%' THEN 'Сбор добычи' WHEN t.functions LIKE '%feeding%' THEN 'Кормление' ELSE 'Остальные' END",
    level: "NULL", grade: "''", icon: "coalesce(t.icon, '')" },
  // a quest's picture is its kind, as the map's marks: «quest:gold» mission, «quest:darkblue» significant/important, «quest:pink» event, «quest:blue» the rest
  quest: { table: "quest", name: "t.name_key", kind: "coalesce(t.category, '')", level: "t.min_level", grade: "''",
    icon: "CASE WHEN t.category LIKE 'mission%' THEN 'quest:gold' WHEN t.category LIKE 'significant%' OR t.category LIKE 'important%' THEN 'quest:darkblue' "
      + "WHEN t.category LIKE 'event%' THEN 'quest:pink' ELSE 'quest:blue' END" },
  recipe: {
    table: "recipe", join: "LEFT JOIN item p ON p.id = t.product", name: "t.name_key", kind: "coalesce(t.profession, '')",
    level: "t.level", grade: "coalesce(p.grade, '')", icon: "coalesce(p.icon, '')",
  },
};

/** The classes of the «Класс» filter: id (the client's), name, the prefixes of its skills' names (its own and its base class'), the keys of a book's classes. */
export const SKILL_CLASSES: [id: string, name: string, prefixes: string[], keys: string[]][] = [
  ["fighter", "Гладиатор", ["FI_", "WA_"], ["fighter", "warrior"]], ["knight", "Страж", ["KN_", "WA_"], ["knight", "warrior"]],
  ["assassin", "Убийца", ["AS_", "SC_"], ["assassin", "scout"]], ["ranger", "Стрелок", ["RA_", "SC_"], ["ranger", "scout"]],
  ["wizard", "Волшебник", ["WI_", "MA_"], ["wizard", "mage"]], ["elementalist", "Заклинатель", ["EL_", "MA_"], ["elementalist", "mage"]],
  ["priest", "Целитель", ["PR_", "CL_"], ["priest", "cleric"]], ["chanter", "Чародей", ["CH_", "CL_"], ["chanter", "cleric"]],
];
/** A skill's family («FI_RobustImpulse_G» of «FI_RobustImpulse_G3») and its level (3), as SQL over a skill-name column. */
const family = (col: string) => `lower(rtrim(${col}, '0123456789'))`;
const rank = (col: string) => `CAST(substr(${col}, length(rtrim(${col}, '0123456789')) + 1) AS INTEGER)`;
const SKILL_TABLE: Record<string, string> = { skill_books: "skill_book", stigmas: "stigma" };

const fold = (text: string) => text.toLowerCase().split("ё").join("е").trim();

async function shapeOf(all: All, section: string): Promise<Shape | null> {
  const [meta] = await all("SELECT entity FROM db_section WHERE key = ?", [section]);
  return (meta && SHAPE[String(meta.entity)]) || null;
}

/** The FROM … WHERE of a section with its filters, and its arguments. */
function filtered(shape: Shape, section: string, options: PageOptions, skip: "kind" | "grade" | "" = ""): [string, unknown[]] {
  const where: string[] = ["e.section = ?"];
  const args: unknown[] = [section];
  const query = fold(options.query ?? "");
  if (query) { where.push(`(${shape.name} LIKE ? OR CAST(t.id AS TEXT) = ?)`); args.push(`%${query}%`, query); }
  if (options.grade && skip !== "grade") { where.push(`${shape.grade} = ?`); args.push(options.grade); }
  if (options.kind && skip !== "kind") { where.push(`${shape.kind} = ?`); args.push(options.kind); }
  if (options.questType) {
    const cats = { gold: ["mission"], blue: ["quest", "task"], darkblue: ["significant", "important"], pink: ["event"] }[options.questType];
    where.push(`(${cats.map(() => "t.category = ? OR t.category LIKE ?").join(" OR ")})`);
    for (const c of cats) args.push(c, `${c} |%`);
  }
  if (options.race === "common") where.push("t.race = 'pc_light,pc_dark'");
  else if (options.race) { where.push("t.race LIKE ?"); args.push(`%pc_${options.race}%`); }
  if (options.levelMin !== undefined) { where.push(`${shape.level} >= ?`); args.push(options.levelMin); }
  if (options.levelMax !== undefined) { where.push(`${shape.level} <= ?`); args.push(options.levelMax); }
  if (options.slot && shape.table === "item") { where.push("t.id IN (SELECT id FROM gear_item WHERE slot = ?)"); args.push(options.slot); }
  const skills = SKILL_TABLE[section];
  const cls = skills && SKILL_CLASSES.find(([id]) => id === options.cls);
  if (cls && skills === "skill_book") {
    where.push(`EXISTS (SELECT 1 FROM skill_book b WHERE b.item_id = t.id AND (${cls[3].map(() => "b.classes LIKE ?").join(" OR ")}))`);
    args.push(...cls[3].map((key) => `%"${key}"%`));
  } else if (cls) {
    where.push(`EXISTS (SELECT 1 FROM stigma g WHERE g.item_id = t.id AND upper(substr(g.skill, 1, 3)) IN (${cls[2].map(() => "?").join(", ")}))`);
    args.push(...cls[2]);
  }
  if (options.best && skills) { // only the rows that teach the highest level of their skill among the section's rows (one pass, not a check per row)
    where.push(`t.id IN (SELECT s1.item_id FROM ${skills} s1 JOIN (SELECT ${family("s2.skill")} AS fam, max(${rank("s2.skill")}) AS top FROM ${skills} s2 `
      + `JOIN db_section_entry e2 ON e2.section = ? AND e2.entity_id = s2.item_id GROUP BY 1) m ON m.fam = ${family("s1.skill")} AND m.top = ${rank("s1.skill")})`);
    args.push(section);
  }
  if (options.hideAbove !== undefined) { where.push(`(${shape.level} IS NULL OR ${shape.level} <= ?)`); args.push(options.hideAbove); }
  return [`FROM db_section_entry e JOIN ${shape.table} t ON t.id = e.entity_id ${shape.join ?? ""} WHERE ${where.join(" AND ")}`, args];
}

/** A page of a section's list: the rows of its ids, filtered, sorted, with the total of the filter. */
export async function sectionPage(all: All, section: string, options: PageOptions = {}): Promise<{ total: number; rows: SectionRow[] }> {
  const shape = await shapeOf(all, section);
  if (!shape) return { total: 0, rows: [] };
  const [base, args] = filtered(shape, section, options);
  const [count] = await all(`SELECT count(*) AS n ${base}`, args);
  const order = options.sort === "level" ? shape.level : options.sort === "id" ? "t.id" : shape.name;
  const dir = options.desc ? "DESC" : "ASC";
  const rows = await all(
    `SELECT t.id, t.name, ${shape.kind} AS kind, ${shape.level} AS level, ${shape.grade} AS grade, ${shape.icon} AS icon ${base} `
    + `ORDER BY ${order} IS NULL, ${order} ${dir}, t.id LIMIT ? OFFSET ?`,
    [...args, options.limit ?? 50, options.offset ?? 0],
  );
  return {
    total: Number(count.n),
    rows: rows.map((r) => ({
      id: Number(r.id), name: String(r.name ?? ""), kind: String(r.kind ?? ""),
      level: r.level === null || r.level === undefined ? null : Number(r.level), grade: String(r.grade ?? ""), icon: String(r.icon ?? ""),
    })),
  };
}

/** The types of a section's rows under the other filters, the most common first: the «Тип» menu. */
export async function sectionKinds(all: All, section: string, options: PageOptions = {}): Promise<[string, number][]> {
  const shape = await shapeOf(all, section);
  if (!shape || shape.kind === "''") return [];
  const [base, args] = filtered(shape, section, options, "kind");
  const rows = await all(`SELECT ${shape.kind} AS kind, count(*) AS n ${base} GROUP BY 1 HAVING ${shape.kind} <> '' ORDER BY n DESC, 1`, args);
  return rows.map((r) => [String(r.kind), Number(r.n)]);
}

/** The grades of a section's rows under the other filters: the «Качество» menu lists only the ones that have rows. */
export async function sectionGrades(all: All, section: string, options: PageOptions = {}): Promise<[string, number][]> {
  const shape = await shapeOf(all, section);
  if (!shape || shape.grade === "''") return [];
  const [base, args] = filtered(shape, section, options, "grade");
  const rows = await all(`SELECT ${shape.grade} AS grade, count(*) AS n ${base} GROUP BY 1 HAVING ${shape.grade} <> ''`, args);
  return rows.map((r) => [String(r.grade), Number(r.n)]);
}
