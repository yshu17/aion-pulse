// The «База данных» tab (docs/concepts/database-tab/a2.html, variant A): the sections as pills, a search with filters,
// the list on the left and the card on the right — an item's card is the game's tooltip (ItemCard.tsx) with where it
// comes from beside it; two ticked items are compared side by side, the better and the worse stats marked.
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { compareStats } from "../../core/items/compare";
import { bonusLine, cleanSkillText } from "../../core/items/statNames";
import type { Block } from "../../core/items/card";
import { entityCard, itemSkill, itemSources, linkParts, questCard, questKind, type ItemSkill, type ItemSources, type QuestCard, type QuestNpc } from "../../core/db/catalogCard";
import { recipe as readRecipe, type Recipe } from "../../core/db/game";
import { SECTION_KEY, SKILL_CLASSES, sectionCounts, sectionGrades, sectionKinds, sectionPage, type PageOptions, type SectionRow } from "../../core/db/sections";
import { TOP } from "../../core/tabs";
import { RARITY } from "../../core/bestiary/card";
import { PickMenu } from "../bestiary/PickMenu";
import { REWARD_KIND, RewardIcon } from "../RewardIcon";
import { CardBody, StatMarks, useSpec } from "../ItemCard";
import { Icon } from "../Icon";
import { IconClose, IconCopy, IconReset, IconSearch } from "../icons";
import { copyText } from "../map/GatherPanel";
import { useOpenRef, type CardRef } from "../map/placeLink";
import { pulseDb, pulseDbSchema } from "./pulseDb";
import "../bestiary/bestiary.css";
import "./dbTab.css";

const PAGE = 100;
const ITEM_SECTIONS = new Set(["items", "weapons", "armour", "jewels", "skill_books", "stigmas"]);
const NO_LEVEL = new Set(["titles", "pets"]);
const ENTITY: Record<string, string> = { titles: "title", pets: "pet", quests: "quest", recipes: "recipe" };
const SECTIONS = TOP.flat().find((t) => t.id === "db")!.menu!.flatMap((g) => g.items);
const GRADES = ["mythic", "epic", "unique", "legend", "rare", "common", "junk"];
const LEVELS: [string, string][] = [["Любой", ""], ["1–10", "1-10"], ["11–20", "11-20"], ["21–30", "21-30"], ["31–40", "31-40"],
  ["41–50", "41-50"], ["51–55", "51-55"], ["56–60", "56-60"], ["61+", "61-999"]];
const SORTS: [string, string][] = [["Уровень ↓", "level-desc"], ["Уровень ↑", "level-asc"], ["Имя А–Я", "name-asc"], ["Имя Я–А", "name-desc"], ["ID", "id-asc"]];
const PROFESSION: Record<string, string> = { weaponsmith: "Оружейник", armorsmith: "Бронник", tailoring: "Портной", handiwork: "Ремесленник",
  alchemy: "Алхимик", cooking: "Кулинар", convert: "Обработка" };
const CLASS_RU: Record<string, string> = { warrior: "Воин", fighter: "Гладиатор", knight: "Страж", scout: "Разведчик", assassin: "Убийца",
  ranger: "Стрелок", mage: "Маг", wizard: "Волшебник", elementalist: "Заклинатель", priest: "Целитель", cleric: "Жрец", chanter: "Чародей" };
// every icon of one kind of place is one size: a list row, the head of a card, a small row of a part or a reward
const ROW_ICON = 36, HEAD_ICON = 48, PART_ICON = 26;
const SLOTS: [string, string][] = [["Любая", ""], ["Верх", "torso"], ["Низ", "pants"], ["Ботинки", "shoes"], ["Плечи", "shoulder"], ["Перчатки", "glove"]];
const SKILL_SECTIONS = new Set(["skill_books", "stigmas"]);
const VENDOR_KIND: Record<string, string> = { trade_info: "за кинары", abyss_trade_info: "за ОБ", extra_currency_trade_info: "за знаки",
  trade_in_trade_info: "обмен", coupon_trade_info: "за купоны" };
const gradeRu = (grade: string) => RARITY[grade] ?? grade;
const QUEST_KIND: Record<string, string> = { mission: "Кампания", quest: "Задание", task: "Ремесленное", event: "Событие", faction: "Фракция",
  significant: "Важное", important: "Важное", non_count: "Прочее" };
/** A quest's line under its name: its kind and region («Кампания · Фоэта»). */
const questLine = (category: string) => { const { kind, zone } = questKind(category); return [QUEST_KIND[kind] ?? kind, zone].filter(Boolean).join(" · "); };

const questIcons = import.meta.glob("../../../../data/ui/quest/*.png", { query: "?url", import: "default", eager: true }) as Record<string, string>;

type QuestMark = "gold" | "blue" | "darkblue" | "pink";
const MARK_FILE: Record<QuestMark, string> = { gold: "mission", blue: "normal", darkblue: "important", pink: "event" };
const MARK_NAME: Record<QuestMark, string> = { gold: "Миссия", blue: "Задание", darkblue: "Важное задание", pink: "Сезонное задание" };
const markOf = (icon: string): QuestMark => { const m = icon.slice(6); return m in MARK_FILE ? m as QuestMark : "blue"; };

/** The quest's mark by its kind: gold mission, blue quest, dark blue important, pink seasonal (the game's map marks). */
function QuestIcon({ mark, size = ROW_ICON }: { mark: QuestMark; size?: number }) {
  const url = questIcons[`../../../../data/ui/quest/${MARK_FILE[mark]}.png`];
  return <span className="dbt-quest-icon" style={{ width: size, height: size }} aria-label={MARK_NAME[mark]}>
    {url && <img src={url} alt="" />}
  </span>;
}
const NUMBER = /[+-]?\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?(?:\s*%|\s*ед\.(?:\s*урона)?|\s*сек\.?|\s*мин\.?|\s*м(?![а-яё]))?/gi;

/** A skill's text with every number that matters marked: damage, healing, range, time, percent («661-665 ед. урона», «25 м», «10 сек.», «+3%»). */
function SkillText({ text }: { text: string }) {
  const parts: (string | { hit: string })[] = [];
  let from = 0;
  for (const m of text.matchAll(NUMBER)) {
    if (m.index > from) parts.push(text.slice(from, m.index));
    parts.push({ hit: m[0] });
    from = m.index + m[0].length;
  }
  if (from < text.length) parts.push(text.slice(from));
  return <>{parts.map((part, i) => (typeof part === "string" ? part : <b key={i} className="dbt-dmg">{part.hit}</b>))}</>;
}

/** A name that opens what it names: an item, a quest or a title in its section, an NPC in «NPC», a zone on the map. */
function RefLink({ kind, id, name, className = "" }: CardRef & { className?: string }) {
  const open = useOpenRef();
  if (!open || !id) return <span className={className}>{name}</span>;
  return <button type="button" className={`dbt-link dbt-link-${kind} ${className}`} title={REF_TITLE[kind]} onClick={() => open({ kind, id, name })}>{name}</button>;
}
const REF_TITLE: Record<CardRef["kind"], string> = { item: "Открыть предмет", quest: "Открыть задание", title: "Открыть титул", npc: "Открыть во вкладке NPC", zone: "Открыть на карте" };
const GUIDE_KIND: Record<string, CardRef["kind"]> = { npcs: "npc", items: "item", zones: "zone" };
const itemLink = (id: number) => `[item:${id};ver2;;;]`;

export function DbTab({ tab, onSection, target = null }: { tab: string; onSection(id: string): void; target?: (CardRef & { n: number }) | null }) {
  const label = tab.slice(3);
  const section = SECTION_KEY[label] ?? "items";
  const items = ITEM_SECTIONS.has(section);
  const [all, setAll] = useState<Awaited<ReturnType<typeof pulseDb>> | undefined>(undefined);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [query, setQuery] = useState("");
  const [typed, setTyped] = useState("");
  const [grade, setGrade] = useState("");
  const [kind, setKind] = useState("");
  const [level, setLevel] = useState("");
  const [questType, setQuestType] = useState<"" | "gold" | "blue" | "darkblue" | "pink">("");
  const [race, setRace] = useState<"" | "light" | "dark" | "common">("");
  const [showHigh, setShowHigh] = useState(false); // items and quests above level 55 are hidden unless this is on
  const [slot, setSlot] = useState(""); // armour: the part of the body
  const [cls, setCls] = useState(""); // skill books and stigmas: the class
  const [best, setBest] = useState(false); // skill books and stigmas: only the highest level of a skill
  const [grades, setGrades] = useState<Set<string> | null>(null); // the grades the section has under the other filters
  const [sort, setSort] = useState(() => (NO_LEVEL.has(section) ? "name-asc" : "level-desc"));
  const [rows, setRows] = useState<SectionRow[]>([]);
  const [total, setTotal] = useState(0);
  const [kinds, setKinds] = useState<[string, number][]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(""); // the list's query failed: an old pulse.db (reload the page) or a broken query
  const [schema, setSchema] = useState(""); // the database is older or newer than the program: what to do about it
  const [selected, setSelected] = useState<SectionRow | null>(null);
  const [ticked, setTicked] = useState<SectionRow[]>([]);
  const asked = useRef(0);
  const loadingMore = useRef(false); // the next page is on its way: scrolling does not ask for it twice

  useEffect(() => { // `all` is a function: kept with an updater, or React would call it
    pulseDb().then((db) => { setAll(() => db); if (db) sectionCounts(db).then(setCounts); }).catch(() => setAll(null));
    pulseDbSchema().then((state) => setSchema(state.found === null ? "" : state.text));
  }, []);
  useEffect(() => { const t = setTimeout(() => setQuery(typed), 160); return () => clearTimeout(t); }, [typed]);
  // another section: its own filters
  useEffect(() => {
    setTyped(""); setQuery(""); setGrade(""); setKind(""); setLevel(""); setSlot(""); setCls(""); setSelected(null); setTicked([]);
    setSort(NO_LEVEL.has(section) ? "name-asc" : "level-desc");
  }, [section]);
  // asked from a card (a name in a quest, a part of a recipe): no filters, the one record searched by its id (a title by its name)
  useEffect(() => {
    if (!target) return;
    const text = target.kind === "title" ? target.name : target.id;
    setGrade(""); setKind(""); setLevel(""); setQuestType(""); setRace(""); setSlot(""); setCls(""); setBest(false); setShowHigh(true); setTicked([]);
    setTyped(text); setQuery(text);
  }, [target?.n]); // eslint-disable-line react-hooks/exhaustive-deps

  const options = useMemo((): PageOptions => {
    const [min, max] = level ? level.split("-").map(Number) : [undefined, undefined];
    const [by, dir] = sort.split("-");
    const cap = (items || section === "quests") && !showHigh && !level ? 55 : undefined; // only items and quests are capped
    const skills = SKILL_SECTIONS.has(section);
    return { query, grade: items ? grade : "", kind, levelMin: min, levelMax: max, hideAbove: cap, sort: by as PageOptions["sort"], desc: dir === "desc",
      questType: section === "quests" && questType ? questType : undefined, race: section === "quests" && race ? race : undefined,
      slot: section === "armour" && slot ? slot : undefined, cls: skills && cls ? cls : undefined, best: skills && best };
  }, [query, grade, kind, level, sort, items, showHigh, section, questType, race, slot, cls, best]);

  const load = useCallback(async (offset: number) => {
    if (!all) return;
    const n = ++asked.current;
    setLoading(true);
    let page: Awaited<ReturnType<typeof sectionPage>>;
    try {
      page = await sectionPage(all, section, { ...options, offset, limit: PAGE });
    } catch (error) {
      if (n !== asked.current) return;
      console.warn("db list", error);
      setRows([]); setTotal(0); setSelected(null); setLoading(false);
      loadingMore.current = false;
      setFailed("Не удалось прочитать раздел: файл базы не подходит программе. Перезапустите программу (на странице разработки: Ctrl+F5).");
      return;
    }
    if (n !== asked.current) return; // a newer search came meanwhile
    setFailed("");
    setTotal(page.total);
    setRows((old) => (offset ? [...old, ...page.rows] : page.rows));
    loadingMore.current = false;
    if (!offset) setSelected((old) => (old && page.rows.some((r) => r.id === old.id) ? old : page.rows[0] ?? null));
    setLoading(false);
  }, [all, section, options]);

  useEffect(() => { void load(0); }, [load]);
  useEffect(() => { if (all) sectionKinds(all, section, { ...options, kind: "" }).then(setKinds).catch(() => setKinds([])); }, [all, section, options]);
  useEffect(() => { // the «Качество» menu lists only the grades that have rows
    if (!all || !items) { setGrades(null); return; }
    let alive = true;
    sectionGrades(all, section, options).then((list) => alive && setGrades(new Set(list.map(([g]) => g)))).catch(() => alive && setGrades(null));
    return () => { alive = false; };
  }, [all, section, options, items]);

  const tick = (row: SectionRow) => setTicked((old) => old.some((r) => r.id === row.id)
    ? old.filter((r) => r.id !== row.id) : [...old, row].slice(-2)); // two at most: a third replaces the oldest
  const reset = () => { setGrade(""); setKind(""); setLevel(""); setTyped(""); setQuestType(""); setRace(""); setSlot(""); setCls(""); setBest(false); };
  const comparing = items && ticked.length === 2;

  return (
    <main className="dbt">
      <nav className="dbt-secs" aria-label="Разделы базы данных">
        {SECTIONS.map((s) => (
          <button key={s.id} type="button" className={`dbt-sec${s.id === tab ? " on" : ""}`} aria-pressed={s.id === tab} onClick={() => onSection(s.id)}>
            {s.label}<em>{counts[s.id] !== undefined ? counts[s.id].toLocaleString("ru-RU") : ""}</em>
          </button>
        ))}
      </nav>
      {schema && <div className="banner warn dbt-schema" role="status">{schema}</div>}
      <div className="bst-bar dbt-bar">
        <div className="bst-search">
          <IconSearch />
          <input className="field" placeholder="Поиск по названию или ID…" value={typed} aria-label={`Поиск: ${label}`}
            onChange={(e) => setTyped(e.target.value)} />
          {typed && <button className="x" aria-label="Очистить поиск" onClick={() => setTyped("")}><IconClose /></button>}
        </div>
        {items && <PickMenu id="db-grade" label="Качество" text={grade ? gradeRu(grade) : "Качество"} lit={!!grade} value={grade} onPick={setGrade}
          tone={(g) => (g ? `g-${g}` : "")}
          options={[["Любое", ""], ...GRADES.filter((g) => !grades || grades.has(g) || g === grade).map((g): [string, string] => [gradeRu(g), g])]} />}
        {section === "armour" && <PickMenu id="db-slot" label="Часть" text={slot ? SLOTS.find(([, v]) => v === slot)![0] : "Часть"} lit={!!slot} value={slot} onPick={setSlot} options={SLOTS} />}
        {SKILL_SECTIONS.has(section) && <PickMenu id="db-class" label="Класс" text={cls ? SKILL_CLASSES.find(([id]) => id === cls)![1] : "Класс"} lit={!!cls} value={cls} onPick={setCls}
          options={[["Все", ""], ...SKILL_CLASSES.map(([id, name]): [string, string] => [name, id])]} />}
        {SKILL_SECTIONS.has(section) && <button type="button" className={`dbt-chip${best ? " on" : ""}`} aria-pressed={best} onClick={() => setBest((v) => !v)}>Только высший уровень</button>}
        {!NO_LEVEL.has(section) && <PickMenu id="db-level" label="Уровень" text={level ? `Ур. ${level.replace("-999", "+").replace("-", "–")}` : "Уровень"}
          lit={!!level} value={level} onPick={setLevel} options={LEVELS} />}
        {section === "quests" && <PickMenu id="db-qtype" label="Вид" text={{ "": "Вид", gold: "Миссии", blue: "Задания", darkblue: "Важные", pink: "Сезонные" }[questType]} lit={!!questType} value={questType} onPick={(v) => setQuestType(v as typeof questType)}
          options={[["Все", ""], ["Миссии (золотой)", "gold"], ["Задания (голубой)", "blue"], ["Важные (тёмно-синий)", "darkblue"], ["Сезонные (розовый)", "pink"]]} />}
        {section === "quests" && <PickMenu id="db-race" label="Раса" text={{ "": "Раса", light: "Элийцы", dark: "Асмодиане", common: "Общие" }[race]} lit={!!race} value={race} onPick={(v) => setRace(v as typeof race)}
          options={[["Все", ""], ["Элийцы", "light"], ["Асмодиане", "dark"], ["Общие", "common"]]} />}
        {(items || section === "quests") && <button type="button" className={`dbt-chip${showHigh ? " on" : ""}`} aria-pressed={showHigh} onClick={() => setShowHigh((v) => !v)}>
          {showHigh ? "Выше 55: показаны" : "Выше 55: скрыты"}</button>}
        {kinds.length > 1 && section !== "quests" && <PickMenu id="db-kind" label={section === "armour" ? "Тип брони" : "Тип"} text={kind ? PROFESSION[kind] ?? kind : section === "armour" ? "Тип брони" : "Тип"} lit={!!kind} value={kind} onPick={setKind}
          options={[["Все", ""], ...kinds.slice(0, 40).map(([k, n]): [string, string] => [`${PROFESSION[k] ?? k} · ${n.toLocaleString("ru-RU")}`, k])]} />}
        {(grade || kind || level || typed || questType || race || slot || cls || best) && <button type="button" className="bst-reset" onClick={reset}><IconReset />Сбросить</button>}
      </div>
      <div className="dbt-body">
        <section className="dbt-list" aria-label={`Список: ${label}`}>
          <div className="dbt-list-head">
            <span className="dbt-count" aria-live="polite"><b>{loading && !rows.length ? "…" : total.toLocaleString("ru-RU")}</b> найдено</span>
            <PickMenu id="db-sort" label="Сортировка" text={SORTS.find(([, v]) => v === sort)?.[0] ?? "Сортировка"} value={sort} onPick={setSort}
              options={NO_LEVEL.has(section) ? SORTS.filter(([, v]) => !v.startsWith("level")) : SORTS} right />
          </div>
          <ul className="dbt-rows" onScroll={(e) => { // the next hundred comes by itself near the end of the list
            const el = e.currentTarget;
            if (loadingMore.current || loading || rows.length >= total || el.scrollTop + el.clientHeight < el.scrollHeight - 600) return;
            loadingMore.current = true;
            void load(rows.length);
          }} onKeyDown={(e) => {
            if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
            const at = rows.findIndex((r) => r.id === selected?.id);
            const next = rows[Math.max(0, Math.min(rows.length - 1, at + (e.key === "ArrowDown" ? 1 : -1)))];
            if (!next) return;
            e.preventDefault();
            setSelected(next);
            (e.currentTarget.querySelector(`[data-row="${next.id}"]`) as HTMLElement | null)?.focus();
          }}>
            {rows.map((row) => {
              const on = ticked.some((r) => r.id === row.id);
              return (
                <li key={row.id} className={`dbt-row${selected?.id === row.id ? " sel" : ""}`}>
                  {items && <input type="checkbox" className="dbt-tick" checked={on} aria-label={`Сравнить: ${row.name}`} onChange={() => tick(row)} />}
                  <button type="button" className="dbt-row-main" data-row={row.id} aria-current={selected?.id === row.id || undefined} onClick={() => setSelected(row)}>
                    {row.icon.startsWith("quest:") ? <QuestIcon mark={markOf(row.icon)} /> : row.icon ? <Icon name={row.icon} size={ROW_ICON} /> : <span className="icon blank dbt-noicon" />}
                    <span className="dbt-row-text">
                      <b className={row.grade ? `g-${row.grade}` : ""}>{row.name || `ID ${row.id}`}</b>
                      <span>{[row.level !== null ? `${section === "recipes" ? "Навык" : "Ур."} ${row.level}` : "", section === "quests" ? questLine(row.kind) : PROFESSION[row.kind] ?? row.kind].filter(Boolean).join(" · ") || `ID ${row.id}`}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {rows.length > 0 && rows.length < total && <div className="dbt-foot">
            <span>Показано {rows.length.toLocaleString("ru-RU")} из {total.toLocaleString("ru-RU")}</span>
            <button type="button" className="dbt-more-link" disabled={loading} onClick={() => void load(rows.length)}>{loading ? "Загружаю…" : "ещё"}</button>
          </div>}
          {all === null && <div className="bst-empty">База игры не найдена: нет файла data/pulse.db.</div>}
          {all && !loading && !rows.length && <div className="bst-empty">{failed || "Ничего не нашлось: проверь слово или сбрось фильтры."}</div>}
        </section>
        <section className="dbt-detail" aria-label="Карточка">
          {comparing && all ? <Compare a={ticked[0]} b={ticked[1]} onClear={() => setTicked([])} />
            : selected && all ? (items
              ? <ItemDetail all={all} row={selected} section={section} ticked={ticked.some((r) => r.id === selected.id)} onTick={() => tick(selected)} />
              : section === "quests" ? <QuestDetail all={all} row={selected} /> : <EntityDetail all={all} entity={ENTITY[section]} row={selected} />)
              : <div className="bst-empty">Выбери запись в списке.</div>}
        </section>
      </div>
    </main>
  );
}

/** The game's tooltip of an item, embedded: its own row fills in when the catalog has no card. */
function Tooltip({ row }: { row: SectionRow }) {
  const answer = useSpec(String(row.id));
  return <CardBody id={String(row.id)} answer={answer} className="in-db" fallback={{ name: row.name, icon: row.icon, grade: row.grade, level: row.level, kind: row.kind }} />;
}

function ItemDetail({ all, row, section, ticked, onTick }: {
  all: NonNullable<Awaited<ReturnType<typeof pulseDb>>>; row: SectionRow; section: string; ticked: boolean; onTick(): void;
}) {
  const [where, setWhere] = useState<ItemSources | null>(null);
  const [skill, setSkill] = useState<ItemSkill | null>(null);
  const [copied, setCopied] = useState(false);
  const [allRecipes, setAllRecipes] = useState(false); // the long lists are folded until asked for
  const [allVendors, setAllVendors] = useState(false);
  useEffect(() => {
    let alive = true;
    setWhere(null); setSkill(null); setCopied(false); setAllRecipes(false); setAllVendors(false);
    itemSources(all, row.id).then((w) => alive && setWhere(w));
    if (section === "skill_books" || section === "stigmas" || section === "items") itemSkill(all, row.id).then((s) => alive && setSkill(s));
    return () => { alive = false; };
  }, [all, row.id, section]);
  const classes = skill ? Object.keys(skill.classes).map((c) => CLASS_RU[c] ?? c) : [];
  const absent = where ? [where.dropTotal ? "" : "С монстров не падает", where.recipes.length ? "" : "Не создаётся", where.vendors.length ? "" : "Не продаётся"].filter(Boolean) : [];
  return (
    <div className="dbt-card dbt-in" key={row.id}>
      <Tooltip row={row} />
      <div className="dbt-side">
        <div className="dbt-tags">
          {row.grade && <span className={`dbt-tag g-${row.grade}`}>{gradeRu(row.grade)}</span>}
          {row.kind && <span className="dbt-tag plain">{row.kind}</span>}
          <span className="dbt-tag plain">ID {row.id}</span>
        </div>
        {skill && (
          <div className="dbt-box">
            <h5>{skill.kind === "book" ? "Учит умению" : "Даёт умение"}</h5>
            <div className="dbt-skill">
              {skill.icon && <Icon name={skill.icon} size={HEAD_ICON} />}
              <b>{skill.name}{skill.level ? ` · ур. ${skill.level}` : ""}</b>
            </div>
            {(skill.damage || skill.description) && <p className="dbt-note"><SkillText text={skill.damage ?? cleanSkillText(skill.description)} /></p>}
            {classes.length > 0 && <p className="dbt-note">Классы: {classes.join(", ")}</p>}
          </div>
        )}
        {!where ? <p className="dbt-note">Загружаю, откуда предмет…</p> : <>
          {where.dropTotal > 0 && (
            <div className="dbt-box">
              <h5>Добыча<em>{where.dropTotal.toLocaleString("ru-RU")}</em></h5>
              {where.drops.map((n) => <div key={n.id} className="dbt-li"><RefLink kind="npc" id={n.id} name={n.name} className="dbt-b" /></div>)}
              {where.dropTotal > where.drops.length && <p className="dbt-note">и ещё {(where.dropTotal - where.drops.length).toLocaleString("ru-RU")} NPC</p>}
            </div>
          )}
          {(where.recipes.length > 0 || where.usedIn > 0) && (
            <div className="dbt-box">
              <h5>Рецепты{where.recipes.length > 0 && <em>{where.recipes.length}</em>}</h5>
              {(allRecipes ? where.recipes : where.recipes.slice(0, 2)).map((r) => (
                <div key={r.id} className="dbt-recipe">
                  <div className="dbt-li"><b>{r.name}</b><span>{PROFESSION[r.profession] ?? r.profession}{r.level ? ` · навык ${r.level}` : ""}</span></div>
                  <Parts parts={r.parts} />
                </div>
              ))}
              {where.recipes.length > 2 && <button type="button" className="dbt-more-link" aria-expanded={allRecipes} onClick={() => setAllRecipes((v) => !v)}>
                {allRecipes ? "Свернуть" : `Показать все рецепты (${where.recipes.length})`}</button>}
              {where.usedIn > 0 && <p className="dbt-note">Нужен в рецептах: {where.usedIn.toLocaleString("ru-RU")}</p>}
            </div>
          )}
          {where.vendors.length > 0 && (
            <div className="dbt-box">
              <h5>Торговцы<em>{where.vendors.length}</em></h5>
              {(allVendors ? where.vendors : where.vendors.slice(0, 5)).map((v) => (
                <div key={`${v.id}-${v.kind}`} className="dbt-li"><RefLink kind="npc" id={v.id} name={v.name} className="dbt-b" /><span>{VENDOR_KIND[v.kind] ?? v.kind}</span></div>
              ))}
              {where.vendors.length > 5 && <button type="button" className="dbt-more-link" aria-expanded={allVendors} onClick={() => setAllVendors((v) => !v)}>
                {allVendors ? "Свернуть" : `Показать всех (${where.vendors.length})`}</button>}
            </div>
          )}
          {absent.length > 0 && <p className="dbt-note dbt-absent">{absent.join(" · ")}</p>}
        </>}
        <div className="dbt-actions">
          <button type="button" className="btn primary" onClick={() => copyText(itemLink(row.id)).then(setCopied)}><IconCopy />{copied ? "Скопировано" : "Копировать ссылку"}</button>
          <button type="button" className={`btn${ticked ? " on" : ""}`} aria-pressed={ticked} onClick={onTick}>{ticked ? "Убрать из сравнения" : "Добавить к сравнению"}</button>
        </div>
      </div>
    </div>
  );
}

/** Two items side by side; each card's stats are marked against the other's. */
function Compare({ a, b, onClear }: { a: SectionRow; b: SectionRow; onClear(): void }) {
  const left = useSpec(String(a.id));
  const right = useSpec(String(b.id));
  const blocks = (answer: ReturnType<typeof useSpec>) => ((answer?.spec?.blocks as Block[] | undefined) ?? []);
  const marksA = compareStats(blocks(left), blocks(right));
  const marksB = compareStats(blocks(right), blocks(left));
  return (
    <div className="dbt-compare">
      <div className="dbt-cmpbar">
        <b>Сравнение: 2 предмета</b>
        <span>{a.name} и {b.name}</span>
        <span className="spacer" />
        <span className="dbt-legend"><span className="up">▲ лучше</span><span className="dn">▼ хуже</span></span>
        <button type="button" className="btn" onClick={onClear}>Снять</button>
      </div>
      <div className="dbt-pair">
        <StatMarks.Provider value={marksA}><CardBody id={String(a.id)} answer={left} className="in-db" fallback={{ name: a.name, icon: a.icon, grade: a.grade, level: a.level, kind: a.kind }} /></StatMarks.Provider>
        <span className="dbt-vs">VS</span>
        <StatMarks.Provider value={marksB}><CardBody id={String(b.id)} answer={right} className="in-db" fallback={{ name: b.name, icon: b.icon, grade: b.grade, level: b.level, kind: b.kind }} /></StatMarks.Provider>
      </div>
    </div>
  );
}

const RACE: Record<string, string> = { pc_light: "Элийцы", pc_dark: "Асмодиане", "pc_light,pc_dark": "Обе стороны" };
const PET_FUNC: Record<string, string> = { warehouse: "Склад", looting: "Сбор добычи", feeding: "Кормление", doping: "Усиление", wrap: "Упаковка" };

/** A title, a pet, a quest or a recipe as a card in the tooltip's style. */
function EntityDetail({ all, entity, row }: { all: NonNullable<Awaited<ReturnType<typeof pulseDb>>>; entity: string; row: SectionRow }) {
  const [card, setCard] = useState<Record<string, any> | null>(null);
  const [made, setMade] = useState<Recipe | null>(null);
  useEffect(() => {
    let alive = true;
    setCard(null); setMade(null);
    entityCard(all, entity, row.id).then((c) => alive && setCard(c));
    if (entity === "recipe") readRecipe(all, String(row.id)).then((r) => alive && setMade(r));
    return () => { alive = false; };
  }, [all, entity, row.id]);
  const stats = entity === "title" && card?.stats ? JSON.parse(card.stats) : null;
  const funcs: string[] = entity === "pet" && card?.functions ? JSON.parse(card.functions) : [];
  const rewards: Record<string, any>[] = entity === "quest" && card?.rewards ? JSON.parse(card.rewards) : [];
  return (
    <div className="dbt-card dbt-in" key={row.id}>
      <div className="item-card in-db dbt-entity" role="region" aria-label={row.name}>
        <div className="ic-title"><b className="ic-name">{row.name}</b></div>
        <div className="ic-top">
          {row.icon && <Icon name={row.icon} size={HEAD_ICON} />}
          <div className="ic-head">
            {!card ? <div className="ic-text muted">Загружаю…</div> : <>
              {entity === "title" && <div className="ic-props">{RACE[card.race] ?? "—"}</div>}
              {entity === "pet" && funcs.length > 0 && <div className="ic-props">{funcs.map((f) => PET_FUNC[f] ?? f).join(", ")}</div>}
              {entity === "quest" && <div className="ic-props">Уровень {card.min_level ?? "?"}{card.max_level ? `–${card.max_level}` : "+"}{card.repeatable ? " · повторяемое" : ""}</div>}
              {entity === "recipe" && <div className="ic-props">{PROFESSION[card.profession] ?? card.profession}{card.level ? ` · навык ${card.level}` : ""}</div>}
            </>}
          </div>
        </div>
        {card?.description && <><hr className="ic-hr" /><p className="ic-text normal">{card.description}</p></>}
        {stats?.bonus?.length > 0 && <><hr className="ic-hr" /><dl className="ic-pairs">{(stats.bonus as string[]).map((b) => {
          const [name, value] = bonusLine(b);
          return <Fragment key={b}><dt>{name}</dt><dd>{value}</dd></Fragment>;
        })}</dl></>}
        {rewards.length > 0 && <><hr className="ic-hr" /><div className="ic-text muted">Награды: {rewards.length}</div></>}
        {made && <>
          <hr className="ic-hr" />
          <div className="dbt-made-title">Результат</div>
          {made.product ? <Parts parts={[{ ...made.product, count: made.count }]} /> : <div className="ic-text muted">Не указан</div>}
          <div className="dbt-made-title">Материалы</div>
          {made.parts.length ? <Parts parts={made.parts} /> : <div className="ic-text muted">Не указаны</div>}
          {made.combo.length > 0 && <div className="ic-text muted">При удаче может выйти другой предмет: {made.combo.length}</div>}
        </>}
        <hr className="ic-hr" /><div className="ic-text muted">ID {row.id}</div>
      </div>
    </div>
  );
}

/** What a recipe needs (or makes): picture, name in its grade's colour, how many. */
function Parts({ parts }: { parts: Recipe["parts"] }) {
  return (
    <ul className="dbt-parts">
      {parts.map((part, i) => (
        <li key={`${part.id}-${i}`}>
          {part.icon ? <Icon name={part.icon} size={PART_ICON} /> : <span className="icon blank dbt-part-blank" />}
          <RefLink kind="item" id={String(part.id)} name={part.name || `ID ${part.id}`} className={part.grade ? `g-${part.grade}` : ""} />
          <b>×{part.count}</b>
        </li>
      ))}
    </ul>
  );
}

const STEP_VERB: Record<string, string> = { kill: "Убить", loot: "Добыть", gather: "Собрать", buy: "Купить", drop: "Добыть", craft: "Создать", after: "Сначала выполнить" };
const RACES: Record<string, string> = { pc_light: "Элийцы", pc_dark: "Асмодиане" };
const REWARD: Record<string, string> = { exp: "Опыт", gold: "Кинары", abyss: "Очки Бездны", abyss_point: "Очки Бездны" };

/** A quest: its mark, the facts (category, race, level, place), who starts and ends it (on the map), the steps, the rewards. */
function QuestDetail({ all, row }: { all: NonNullable<Awaited<ReturnType<typeof pulseDb>>>; row: SectionRow }) {
  const [card, setCard] = useState<QuestCard | null | undefined>(undefined);
  useEffect(() => { let alive = true; setCard(undefined); questCard(all, row.id).then((c) => alive && setCard(c)); return () => { alive = false; }; }, [all, row.id]);
  const npcLine = (label: string, npc: QuestNpc | null, fallbackName = "") => (
    <div className="dbt-npc">
      <span className="dbt-npc-label">{label}</span>
      {npc ? <>
        <RefLink kind="npc" id={npc.id} name={npc.name} className="dbt-b" />
        {npc.zone && <span className="dbt-npc-zone">{npc.zone}</span>}
      </> : fallbackName ? <b>{fallbackName}</b> : <span className="dbt-npc-zone">в данных не указан</span>}
    </div>
  );
  const guide = card?.guide ?? null;
  const mark: QuestMark = card?.gold ? "gold" : markOf(row.icon);
  const levels = card ? `${guide?.level ?? card.min_level ?? "?"}${card.max_level ? `–${card.max_level}` : ""}` : ""; // aidb's level first: the client's minimum can differ
  const classes = guide ? (guide.classes.length >= 14 ? "Все классы" : guide.classes.join(", ")) : "";
  const before = (card?.steps ?? []).filter((step) => step.do === "after").flatMap((step) => step.quests ?? []); // the quests this one waits for
  return (
    <div className="dbt-card dbt-quest dbt-in" key={row.id}>
      <div className="item-card in-db dbt-entity" role="region" aria-label={row.name}>
        <div className="ic-title dbt-quest-title">
          <QuestIcon mark={mark} size={HEAD_ICON} />
          <div className="dbt-quest-names"><b className={`ic-name dbt-${mark}`}>{row.name}</b>{guide?.name_en && <span>{guide.name_en}</span>}</div>
        </div>
        {card === undefined ? <div className="ic-text muted">Загружаю…</div> : !card ? <div className="ic-text muted">Задания нет в базе.</div> : <>
          <dl className="ic-pairs">
            <dt>Категория</dt><dd>{guide?.category || questLine(`${card.kind}|${card.zone}`)}</dd>
            {(guide?.race || card.races.length > 0) && <><dt>Раса</dt><dd>{guide?.race || (card.races.length > 1 ? "Обе" : RACES[card.races[0]] ?? card.races[0])}</dd></>}
            <dt>Уровень</dt><dd>{levels}{guide?.rec_level ? <span className="dbt-rec"> · рек. {guide.rec_level}</span> : null}</dd>
            {(guide?.zone || card.zone) && <><dt>Локация</dt><dd>{guide?.zoneId ? <RefLink kind="zone" id={guide.zoneId} name={guide.zone || card.zone} /> : guide?.zone || card.zone}</dd></>}
            {classes && <><dt>Классы</dt><dd>{classes}</dd></>}
            {(guide?.repeat || card.repeatable) && <><dt>Повтор</dt><dd>{guide?.repeat || "можно повторять"}</dd></>}
          </dl>
          {guide && guide.notes.length > 0 && <div className="ic-text muted">{guide.notes.join(" ")}</div>}
          <hr className="ic-hr" />
          {npcLine("Берётся у", card.giver, guide?.giverName)}
          {(card.ender || guide?.enderName) && npcLine("Сдать", card.ender, guide?.enderName)}
          {guide && guide.needs.length > 0 && <>
            <div className="dbt-made-title">Нужны предметы</div>
            <ul className="dbt-parts">{guide.needs.map((n) => (
              <li key={n.id}>{n.icon ? <Icon name={n.icon} size={PART_ICON} /> : <span className="icon blank dbt-part-blank" />}<RefLink kind="item" id={n.id} name={n.name} className={n.grade ? `g-${n.grade}` : ""} /><b>×{n.count}</b></li>))}</ul>
          </>}
          <hr className="ic-hr" />
          {before.length > 0 && <>
            <div className="dbt-made-title">Сначала выполнить</div>
            <ul className="dbt-before">{before.map((q) => <li key={q.id}><RefLink kind="quest" id={q.id} name={q.name} /></li>)}</ul>
          </>}
          <div className="dbt-made-title">Прохождение</div>
          {guide?.steps.length ? <ol className="dbt-steps">{guide.steps.map((st, i) => (
            <li key={i}>{linkParts(st.text, st.links).map((part, j) => (typeof part === "string" ? part
              : <RefLink key={j} kind={GUIDE_KIND[part.kind] ?? "npc"} id={part.id} name={part.name} />))}</li>))}</ol>
            : card.steps.length ? <ol className="dbt-steps">
              {card.steps.map((step, i) => (
                <li key={i}>
                  <span className="dbt-step-verb">{STEP_VERB[step.do] ?? step.do}</span>
                  {step.do === "after" && <span>{(step.quests ?? []).map((q, j) => <Fragment key={q.id}>{j ? ", " : ""}<RefLink kind="quest" id={q.id} name={q.name} /></Fragment>)}</span>}
                  {step.do === "craft" && <span>{PROFESSION[step.skill ?? ""] ?? "предмет ремеслом"}{step.level ? `, навык ${step.level}` : ""}</span>}
                  {step.item && <span className="dbt-step-item">
                    {step.item.icon && <Icon name={step.item.icon} size={PART_ICON} />}
                    <RefLink kind="item" id={step.item.id} name={step.item.name} className={step.item.grade ? `g-${step.item.grade}` : ""} />
                    {step.count ? <b>×{step.count}</b> : null}
                  </span>}
                  {step.from && (step.from.length > 0 || (step.more ?? 0) > 0) && <span className="dbt-step-from">
                    {step.do === "buy" ? "у " : step.do === "kill" || step.do === "gather" ? "" : "с "}
                    {step.from.map((n, j) => <Fragment key={n.id}>{j ? ", " : ""}<RefLink kind="npc" id={n.id} name={n.name} /></Fragment>)}
                    {step.more ? (step.from.length ? ` и ещё ${step.more}` : `${step.more} видов`) : ""}
                  </span>}
                </li>
              ))}
            </ol> : <div className="ic-text muted">Описания прохождения нет: только выдать и сдать.</div>}
          {(card.rewards.length > 0 || guide?.title || (guide?.choice.length ?? 0) > 0) && <>
            <hr className="ic-hr" />
            <div className="dbt-made-title">Награда</div>
            <ul className="dbt-parts">
              {card.rewards.map((r, i) => r.item
                ? <li key={i}>{r.item.icon ? <Icon name={r.item.icon} size={PART_ICON} /> : <span className="icon blank dbt-part-blank" />}<RefLink kind="item" id={r.item.id} name={r.item.name} className={r.item.grade ? `g-${r.item.grade}` : ""} /><b>{r.choice ? "на выбор · " : ""}×{r.amount}</b></li>
                : <li key={i}><span className="reward-name">{REWARD_KIND[r.type] && <RewardIcon kind={REWARD_KIND[r.type]} />}{REWARD[r.type] ?? r.type}</span><b>{r.amount.toLocaleString("ru-RU")}</b></li>)}
              {card.rewards.every((r) => !r.item) && (guide?.choice ?? []).map((c) => (
                <li key={`c${c.id}`}>{c.icon ? <Icon name={c.icon} size={PART_ICON} /> : <span className="icon blank dbt-part-blank" />}<RefLink kind="item" id={c.id} name={c.name} className={c.grade ? `g-${c.grade}` : ""} /><b>на выбор · ×{c.count}</b></li>))}
              {guide?.title && <li><span>Титул</span><RefLink kind="title" id={guide.title} name={guide.title} className="dbt-title-reward dbt-b" /></li>}
            </ul>
          </>}
          <hr className="ic-hr" /><div className="ic-text muted">ID {row.id}{guide ? " · описание: aidb.ru" : ""}</div>
        </>}
      </div>
    </div>
  );
}
