/**
 * How many records each database section has, for the «База данных» menu (pulse.db, one query).
 *
 *   sectionCounts(all) -> { "db:Предметы": n, ... }   only the sections the database already holds
 */

import type { All } from "./npcPoints";

/** The item categories counted as armour (shields and headgear are their own kinds). */
const ARMOUR = ["Ткань", "Кожа", "Кольчуга", "Лата"];

export async function sectionCounts(all: All): Promise<Record<string, number>> {
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
