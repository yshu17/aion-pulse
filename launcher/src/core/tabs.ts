/**
 * The top tabs of Pulse+ (docs/concepts/top-tabs/TOP_TABS_CONCEPT.md, variant 2 of npc-tab.html): three groups split by
 * thin lines — the places (Чат, Карта, NPC, Расписание), the two menus (Калькуляторы, База данных) and the guides.
 * A menu's entries are screens of their own; their ids carry the menu («db:Броня» is not «calc:Броня»).
 *
 *   TOP: TopTab[][]             the groups, left to right
 *   tabLabel(id) -> string      what a screen is called
 *   menuOf(id) -> string|null   the menu a screen lies in, null for a plain tab
 *   LIVE_TABS                   the screens that exist; the others say «будет следующей»
 *   BETA                        the tabs and screens still being tested: a small «beta» mark is drawn beside their name
 */

export interface Section { id: string; label: string }
export interface MenuGroup { title: string; items: Section[] }
export interface TopTab { id: string; label: string; menu?: MenuGroup[] }

const sections = (prefix: string, labels: string[]): Section[] => labels.map((label) => ({ id: `${prefix}:${label}`, label }));

export const TOP: TopTab[][] = [
  [{ id: "Чат", label: "Чат" }, { id: "Карта", label: "Карта" }, { id: "NPC", label: "NPC" }, { id: "Расписание", label: "Расписание" }],
  [
    { id: "calc", label: "Калькуляторы", menu: [{ title: "", items: sections("calc", ["Экипировка", "Стигмы", "Крафт"]) }] },
    { id: "db", label: "База данных", menu: [
      { title: "Предметы", items: sections("db", ["Предметы", "Оружие", "Броня", "Украшения"]) },
      { title: "Знания", items: sections("db", ["Книги умений", "Стигмы", "Титулы", "Питомцы"]) },
      { title: "Мир", items: sections("db", ["Задания", "Рецепты"]) },
    ] },
  ],
  [{ id: "Гайды", label: "Гайды" }],
];

export const LIVE_TABS = ["Чат", "Карта", "NPC", "Расписание", "calc:Экипировка"];

/** «db» is the whole menu (every section of «База данных»), «calc:Экипировка» is one screen of «Калькуляторы». */
export const BETA: ReadonlySet<string> = new Set(["db", "calc:Экипировка"]);

/** A screen is beta by itself or because the menu it lies in is: the id of a «db:…» section counts as «db». */
export const isBeta = (id: string): boolean => BETA.has(id) || BETA.has(id.split(":")[0]);

const owner = (id: string): TopTab | undefined =>
  TOP.flat().find((tab) => tab.id === id || tab.menu?.some((g) => g.items.some((s) => s.id === id)));

export function tabLabel(id: string): string {
  const tab = owner(id);
  if (!tab) return id;
  if (tab.id === id) return tab.label;
  return tab.menu!.flatMap((g) => g.items).find((s) => s.id === id)!.label;
}

export function menuOf(id: string): string | null {
  const tab = owner(id);
  return tab?.menu ? tab.label : null;
}
