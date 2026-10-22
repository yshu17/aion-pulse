/**
 * State of the «Что искать» list without a window: sections, filters, search and the checked items — the port of
 * core/items/browser.py.
 *
 *   new ItemBrowser(items, checked, collapsed, filter)
 *     .shown / .visible           sections and ids after the filter, in display order
 *     .checked                    watched ids (filtered-out items stay checked)
 *     .search(query) -> count;    .step(+1 / -1) -> current match id (null without matches)
 *     .setAll / .setGroup / .toggleItem / .groupChecked / .toggleCollapsed / .expandFor
 *     .toggleGrade(grade), .withLevelsType(low, high, kind), .typeChoices(), .chipState(grade, enabled)
 */

import { normalize } from "../chat/matcher";
import { pyMod, pySplit } from "../py";
import { CATEGORY_ORDER, WatchItem } from "./catalog";

export const PINNED_GROUP = "Рудра и Фланас"; // their gear is pulled out of its sections into this one, on top
export const PINNED_RE = /рудр|фланас/i;
export const GRADE_ORDER = ["finality", "mythic", "epic", "unique", "legend", "rare", "common"];
export const GRADE_LABELS: Record<string, string> = {
  finality: "Финал.", mythic: "Миф.", epic: "Эпич.", unique: "Уник.", legend: "Легенд.", rare: "Редк.", common: "Обыч.",
};
export const ALL_TYPES = "Все типы";
export const ANY_LEVEL = "любой";

export class ItemFilter {
  constructor(
    public grades: Set<string> = new Set(), // shown grades; empty = all
    public level_min = 0, // 0 = any
    public level_max = 0,
    public type = "", // "" all, a section («Лата») or «Оружие: Меч»
  ) {}

  accepts(item: WatchItem): boolean {
    if (this.grades.size && !this.grades.has(item.grade)) return false;
    if (this.level_min && item.level < this.level_min) return false;
    if (this.level_max && item.level > this.level_max) return false;
    if (this.type) {
      const sep = this.type.indexOf(": ");
      const category = sep < 0 ? this.type : this.type.slice(0, sep);
      const kind = sep < 0 ? "" : this.type.slice(sep + 2);
      if (item.category !== category || (kind && item.kind !== kind)) return false;
    }
    return true;
  }

  get active(): boolean {
    return Boolean(this.grades.size || this.level_min || this.level_max || this.type);
  }
}

export class ItemBrowser {
  filter: ItemFilter;
  groups = new Map<string, WatchItem[]>();
  group_of = new Map<string, string>();
  by_id = new Map<string, WatchItem>();
  order: string[] = [];
  checked: Set<string>;
  collapsed: string[];
  matches: string[] = [];
  match_index = -1;
  grades: string[];
  levels: number[];
  shown = new Map<string, WatchItem[]>();
  visible: string[] = [];
  private norm = new Map<string, string>();

  constructor(items: Iterable<WatchItem>, checked: Iterable<string> = [], collapsed: Iterable<string> = [],
              filter: ItemFilter | null = null) {
    this.filter = filter ?? new ItemFilter();
    const groups = new Map<string, WatchItem[]>();
    for (const item of items) {
      const group = PINNED_RE.test(item.name) ? PINNED_GROUP : item.category;
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group)!.push(item);
      this.group_of.set(item.id, group);
    }
    const rank = new Map([PINNED_GROUP, ...CATEGORY_ORDER].map((name, i) => [name, i]));
    const unknown = rank.size;
    const sorted = [...groups.entries()].sort(([a], [b]) => (rank.get(a) ?? unknown) - (rank.get(b) ?? unknown));
    this.groups = new Map(sorted);
    for (const group of this.groups.values()) for (const item of group) this.by_id.set(item.id, item);
    this.order = [...this.groups.values()].flat().map((item) => item.id);
    for (const item of this.by_id.values()) this.norm.set(item.id, normalize(item.name));
    this.checked = new Set([...checked].filter((id) => this.by_id.has(id)));
    this.collapsed = [...collapsed].filter((name) => this.groups.has(name));
    const present = new Set([...this.by_id.values()].map((item) => item.grade));
    this.grades = GRADE_ORDER.filter((grade) => present.has(grade));
    this.levels = [...new Set([...this.by_id.values()].map((item) => item.level))].sort((a, b) => a - b);
    this.relayout();
  }

  // --- list -----------------------------------------------------------------------------
  relayout(): void {
    this.shown = new Map();
    for (const [category, items] of this.groups) {
      const kept = items.filter((item) => this.filter.accepts(item));
      if (kept.length) this.shown.set(category, kept);
    }
    this.visible = [...this.shown.values()].flat().map((item) => item.id);
  }

  checkedIds(): string[] {
    return this.order.filter((id) => this.checked.has(id));
  }

  typeChoices(): string[] {
    const choices = [ALL_TYPES];
    const all = [...this.groups.values()].flat();
    for (const category of CATEGORY_ORDER) {
      const items = all.filter((item) => item.category === category);
      if (!items.length) continue;
      choices.push(category);
      const kinds = [...new Set(items.map((item) => item.kind).filter(Boolean))].sort();
      for (const kind of kinds) choices.push(`${category}: ${kind}`);
    }
    return choices;
  }

  // --- checking and folding ---------------------------------------------------------------
  setAll(value: boolean): void {
    for (const id of this.visible) value ? this.checked.add(id) : this.checked.delete(id);
  }

  setGroup(category: string, value: boolean): void {
    for (const item of this.shown.get(category) ?? []) value ? this.checked.add(item.id) : this.checked.delete(item.id);
  }

  toggleItem(id: string): void {
    this.checked.has(id) ? this.checked.delete(id) : this.checked.add(id);
  }

  groupChecked(category: string): boolean {
    const items = this.shown.get(category) ?? [];
    return items.length > 0 && items.every((item) => this.checked.has(item.id));
  }

  toggleCollapsed(category: string): void {
    const at = this.collapsed.indexOf(category);
    if (at >= 0) this.collapsed.splice(at, 1);
    else this.collapsed.push(category);
  }

  /** Unfold the section of an item; true when it was folded. */
  expandFor(id: string): boolean {
    const at = this.collapsed.indexOf(this.group_of.get(id)!);
    if (at < 0) return false;
    this.collapsed.splice(at, 1);
    return true;
  }

  // --- search -------------------------------------------------------------------------------
  /** Shown items whose name holds every word of the query (a number also matches the level). */
  search(query: string): number {
    const words = pySplit(normalize(query));
    this.matches = !words.length ? [] : this.visible.filter((id) =>
      words.every((w) => this.norm.get(id)!.includes(w) || w === String(this.by_id.get(id)!.level)));
    this.match_index = this.matches.length ? 0 : -1;
    return this.matches.length;
  }

  step(delta: number): string | null {
    if (!this.matches.length) return null;
    this.match_index = pyMod(this.match_index + delta, this.matches.length);
    return this.matches[this.match_index];
  }

  currentMatch(): string | null {
    return this.matches.length ? this.matches[this.match_index] : null;
  }

  // --- filter -------------------------------------------------------------------------------
  setFilter(filter: ItemFilter): void {
    this.filter = filter;
    this.relayout();
  }

  chipState(grade: string, enabled = true): "on" | "off" | "disabled" {
    if (!enabled) return "disabled";
    return !this.filter.grades.size || this.filter.grades.has(grade) ? "on" : "off";
  }

  /** The filter after a click on a grade chip (all grades shown = an empty set). */
  toggleGrade(grade: string): ItemFilter {
    const shown = new Set(this.filter.grades.size ? this.filter.grades : this.grades);
    shown.has(grade) ? shown.delete(grade) : shown.add(grade);
    const all = this.grades.every((g) => shown.has(g));
    return new ItemFilter(all ? new Set() : shown, this.filter.level_min, this.filter.level_max, this.filter.type);
  }

  /** The filter after the level or type boxes changed (a reversed range is swapped, «Все типы» = no type). */
  withLevelsType(low: number, high: number, kind: string): ItemFilter {
    if (low && high && low > high) [low, high] = [high, low];
    return new ItemFilter(new Set(this.filter.grades), low, high, kind === ALL_TYPES ? "" : kind);
  }
}
