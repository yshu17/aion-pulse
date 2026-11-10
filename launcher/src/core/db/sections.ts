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
  title: { table: "title", name: "t.name_key", kind: "''", level: "NULL", grade: "''", icon: "''" },
  pet: { table: "pet", name: "t.name_key", kind: "''", level: "NULL", grade: "''", icon: "coalesce(t.icon, '')" },
  // a quest's picture is its kind: «quest:gold» for a mission (the campaign), «quest:blue» for the rest (catalogCard.questKind)
  quest: { table: "quest", name: "t.name_key", kind: "coalesce(t.category, '')", level: "t.min_level", grade: "''",
    icon: "CASE WHEN t.category LIKE 'mission%' THEN 'quest:gold' ELSE 'quest:blue' END" },
  recipe: {
    table: "recipe", join: "LEFT JOIN item p ON p.id = t.product", name: "t.name_key", kind: "coalesce(t.profession, '')",
    level: "t.level", grade: "coalesce(p.grade, '')", icon: "coalesce(p.icon, '')",
  },
};

const fold = (text: string) => text.toLowerCase().split("ё").join("е").trim();

async function shapeOf(all: All, section: string): Promise<Shape | null> {
  const [meta] = await all("SELECT entity FROM db_section WHERE key = ?", [section]);
  return (meta && SHAPE[String(meta.entity)]) || null;
}

/** The FROM … WHERE of a section with its filters, and its arguments. */
function filtered(shape: Shape, section: string, options: PageOptions, skip: "kind" | "" = ""): [string, unknown[]] {
  const where: string[] = ["e.section = ?"];
  const args: unknown[] = [section];
  const query = fold(options.query ?? "");
  if (query) { where.push(`(${shape.name} LIKE ? OR CAST(t.id AS TEXT) = ?)`); args.push(`%${query}%`, query); }
  if (options.grade) { where.push(`${shape.grade} = ?`); args.push(options.grade); }
  if (options.kind && skip !== "kind") { where.push(`${shape.kind} = ?`); args.push(options.kind); }
  if (options.levelMin !== undefined) { where.push(`${shape.level} >= ?`); args.push(options.levelMin); }
  if (options.levelMax !== undefined) { where.push(`${shape.level} <= ?`); args.push(options.levelMax); }
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
  const rows = await all(`SELECT ${shape.kind} AS kind, count(*) AS n ${base} GROUP BY 1 HAVING kind <> '' ORDER BY n DESC, kind`, args);
  return rows.map((r) => [String(r.kind), Number(r.n)]);
}
