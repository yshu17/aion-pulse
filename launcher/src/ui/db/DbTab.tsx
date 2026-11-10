// The «База данных» tab (docs/concepts/database-tab/a2.html, variant A): the sections as pills, a search with filters,
// the list on the left and the card on the right — an item's card is the game's tooltip (ItemCard.tsx) with where it
// comes from beside it; two ticked items are compared side by side, the better and the worse stats marked.
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { compareStats } from "../../core/items/compare";
import { bonusLine, cleanSkillText } from "../../core/items/statNames";
import type { Block } from "../../core/items/card";
import { entityCard, itemSkill, itemSources, questCard, questKind, type ItemSkill, type ItemSources, type QuestCard, type QuestNpc } from "../../core/db/catalogCard";
import { recipe as readRecipe, type Recipe } from "../../core/db/game";
import { SECTION_KEY, sectionCounts, sectionKinds, sectionPage, type PageOptions, type SectionRow } from "../../core/db/sections";
import { TOP } from "../../core/tabs";
import { RARITY } from "../../core/bestiary/card";
import { PickMenu } from "../bestiary/PickMenu";
import { CardBody, StatMarks, useSpec } from "../ItemCard";
import { Icon } from "../Icon";
import { IconClose, IconCopy, IconReset, IconSearch } from "../icons";
import { copyText } from "../map/GatherPanel";
import { useOpenMap } from "../map/placeLink";
import { IconPin } from "../icons";
import { pulseDb } from "./pulseDb";
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
  ranger: "Стрелок", mage: "Маг", wizard: "Волшебник", elementalist: "Заклинатель", priest: "Жрец", cleric: "Целитель", chanter: "Чародей" };
const VENDOR_KIND: Record<string, string> = { trade_info: "за кинары", abyss_trade_info: "за ОБ", extra_currency_trade_info: "за знаки",
  trade_in_trade_info: "обмен", coupon_trade_info: "за купоны" };
const gradeRu = (grade: string) => RARITY[grade] ?? grade;
const QUEST_KIND: Record<string, string> = { mission: "Кампания", quest: "Задание", task: "Ремесленное", event: "Событие", faction: "Фракция",
  significant: "Важное", important: "Важное", non_count: "Прочее" };
/** A quest's line under its name: its kind and region («Кампания · Фоэта»). */
const questLine = (category: string) => { const { kind, zone } = questKind(category); return [QUEST_KIND[kind] ?? kind, zone].filter(Boolean).join(" · "); };

const questIcons = import.meta.glob("../../../../data/ui/quest/*.png", { query: "?url", import: "default", eager: true }) as Record<string, string>;

/** The quest's mark: the gold one for a mission (the campaign), the blue one for the other quests (aidb.ru's own pictures). */
function QuestIcon({ gold, size = 36 }: { gold: boolean; size?: number }) {
  const url = questIcons[`../../../../data/ui/quest/${gold ? "mission" : "normal"}.png`];
  return <span className="dbt-quest-icon" style={{ width: size, height: size }} aria-label={gold ? "Миссия" : "Задание"}>
    {url && <img src={url} alt="" />}
  </span>;
}
const itemLink = (id: number) => `[item:${id};ver2;;;]`;

export function DbTab({ tab, onSection }: { tab: string; onSection(id: string): void }) {
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
  const [sort, setSort] = useState(() => (NO_LEVEL.has(section) ? "name-asc" : "level-desc"));
  const [rows, setRows] = useState<SectionRow[]>([]);
  const [total, setTotal] = useState(0);
  const [kinds, setKinds] = useState<[string, number][]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SectionRow | null>(null);
  const [ticked, setTicked] = useState<SectionRow[]>([]);
  const asked = useRef(0);

  useEffect(() => { // `all` is a function: kept with an updater, or React would call it
    pulseDb().then((db) => { setAll(() => db); if (db) sectionCounts(db).then(setCounts); }).catch(() => setAll(null));
  }, []);
  useEffect(() => { const t = setTimeout(() => setQuery(typed), 160); return () => clearTimeout(t); }, [typed]);
  // another section: its own filters
  useEffect(() => {
    setTyped(""); setQuery(""); setGrade(""); setKind(""); setLevel(""); setSelected(null); setTicked([]);
    setSort(NO_LEVEL.has(section) ? "name-asc" : "level-desc");
  }, [section]);

  const options = useMemo((): PageOptions => {
    const [min, max] = level ? level.split("-").map(Number) : [undefined, undefined];
    const [by, dir] = sort.split("-");
    return { query, grade: items ? grade : "", kind, levelMin: min, levelMax: max, sort: by as PageOptions["sort"], desc: dir === "desc" };
  }, [query, grade, kind, level, sort, items]);

  const load = useCallback(async (offset: number) => {
    if (!all) return;
    const n = ++asked.current;
    setLoading(true);
    const page = await sectionPage(all, section, { ...options, offset, limit: PAGE });
    if (n !== asked.current) return; // a newer search came meanwhile
    setTotal(page.total);
    setRows((old) => (offset ? [...old, ...page.rows] : page.rows));
    if (!offset) setSelected((old) => (old && page.rows.some((r) => r.id === old.id) ? old : page.rows[0] ?? null));
    setLoading(false);
  }, [all, section, options]);

  useEffect(() => { void load(0); }, [load]);
  useEffect(() => { if (all) sectionKinds(all, section, { ...options, kind: "" }).then(setKinds); }, [all, section, options]);

  const tick = (row: SectionRow) => setTicked((old) => old.some((r) => r.id === row.id)
    ? old.filter((r) => r.id !== row.id) : [...old, row].slice(-2)); // two at most: a third replaces the oldest
  const reset = () => { setGrade(""); setKind(""); setLevel(""); setTyped(""); };
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
      <div className="bst-bar dbt-bar">
        <div className="bst-search">
          <IconSearch />
          <input className="field" placeholder="Поиск по названию или ID…" value={typed} aria-label={`Поиск: ${label}`}
            onChange={(e) => setTyped(e.target.value)} />
          {typed && <button className="x" aria-label="Очистить поиск" onClick={() => setTyped("")}><IconClose /></button>}
        </div>
        {items && <PickMenu id="db-grade" label="Качество" text={grade ? gradeRu(grade) : "Качество"} lit={!!grade} value={grade} onPick={setGrade}
          options={[["Любое", ""], ...GRADES.map((g): [string, string] => [gradeRu(g), g])]} />}
        {!NO_LEVEL.has(section) && <PickMenu id="db-level" label="Уровень" text={level ? `Ур. ${level.replace("-999", "+").replace("-", "–")}` : "Уровень"}
          lit={!!level} value={level} onPick={setLevel} options={LEVELS} />}
        {kinds.length > 1 && <PickMenu id="db-kind" label="Тип" text={kind ? `Тип: ${PROFESSION[kind] ?? kind}` : "Тип"} lit={!!kind} value={kind} onPick={setKind}
          options={[["Все", ""], ...kinds.slice(0, 40).map(([k, n]): [string, string] => [`${PROFESSION[k] ?? k} · ${n.toLocaleString("ru-RU")}`, k])]} />}
        {(grade || kind || level || typed) && <button type="button" className="bst-reset" onClick={reset}><IconReset />Сбросить</button>}
      </div>
      <div className="dbt-body">
        <section className="dbt-list" aria-label={`Список: ${label}`}>
          <div className="dbt-list-head">
            <span className="dbt-count" aria-live="polite"><b>{loading && !rows.length ? "…" : total.toLocaleString("ru-RU")}</b> найдено</span>
            <PickMenu id="db-sort" label="Сортировка" text={SORTS.find(([, v]) => v === sort)?.[0] ?? "Сортировка"} value={sort} onPick={setSort}
              options={NO_LEVEL.has(section) ? SORTS.filter(([, v]) => !v.startsWith("level")) : SORTS} right />
          </div>
          <ul className="dbt-rows">
            {rows.map((row) => {
              const on = ticked.some((r) => r.id === row.id);
              return (
                <li key={row.id} className={`dbt-row${selected?.id === row.id ? " sel" : ""}`}>
                  {items && <input type="checkbox" className="dbt-tick" checked={on} aria-label={`Сравнить: ${row.name}`} onChange={() => tick(row)} />}
                  <button type="button" className="dbt-row-main" onClick={() => setSelected(row)}>
                    {row.icon.startsWith("quest:") ? <QuestIcon gold={row.icon === "quest:gold"} /> : row.icon ? <Icon name={row.icon} size={36} /> : <span className="icon blank dbt-noicon" />}
                    <span className="dbt-row-text">
                      <b className={row.grade ? `g-${row.grade}` : ""}>{row.name || `ID ${row.id}`}</b>
                      <span>{[row.level !== null ? `${section === "recipes" ? "Навык" : "Ур."} ${row.level}` : "", section === "quests" ? questLine(row.kind) : PROFESSION[row.kind] ?? row.kind].filter(Boolean).join(" · ") || `ID ${row.id}`}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {!loading && rows.length < total && <button className="btn dbt-more" onClick={() => void load(rows.length)}>Показать ещё ({(total - rows.length).toLocaleString("ru-RU")})</button>}
          {all === null && <div className="bst-empty">База игры не найдена: нет файла data/pulse.db.</div>}
          {all && !loading && !rows.length && <div className="bst-empty">Ничего не нашлось: проверь слово или сбрось фильтры.</div>}
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
  useEffect(() => {
    let alive = true;
    setWhere(null); setSkill(null); setCopied(false);
    itemSources(all, row.id).then((w) => alive && setWhere(w));
    if (section === "skill_books" || section === "stigmas" || section === "items") itemSkill(all, row.id).then((s) => alive && setSkill(s));
    return () => { alive = false; };
  }, [all, row.id, section]);
  const classes = skill ? Object.keys(skill.classes).map((c) => CLASS_RU[c] ?? c) : [];
  return (
    <div className="dbt-card">
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
              {skill.icon && <Icon name={skill.icon} size={32} />}
              <b>{skill.name}{skill.level ? ` · ур. ${skill.level}` : ""}</b>
            </div>
            {skill.description && <p className="dbt-note">{cleanSkillText(skill.description)}</p>}
            {classes.length > 0 && <p className="dbt-note">Классы: {classes.join(", ")}</p>}
          </div>
        )}
        <div className="dbt-box">
          <h5>Добыча</h5>
          {!where ? <p className="dbt-note">Загружаю…</p> : where.dropTotal ? <>
            {where.drops.map((n) => <div key={n.id} className="dbt-li"><b>{n.name}</b></div>)}
            {where.dropTotal > where.drops.length && <p className="dbt-note">и ещё {(where.dropTotal - where.drops.length).toLocaleString("ru-RU")} NPC</p>}
          </> : <p className="dbt-note">С монстров не падает.</p>}
        </div>
        <div className="dbt-box">
          <h5>Рецепты</h5>
          {!where ? <p className="dbt-note">Загружаю…</p> : where.recipes.length ? where.recipes.slice(0, 3).map((r) => (
            <div key={r.id} className="dbt-recipe">
              <div className="dbt-li"><b>{r.name}</b><span>{PROFESSION[r.profession] ?? r.profession}{r.level ? ` · навык ${r.level}` : ""}</span></div>
              <Parts parts={r.parts} />
            </div>
          )) : <p className="dbt-note">Не создаётся.</p>}
          {where && where.recipes.length > 3 && <p className="dbt-note">и ещё рецептов: {where.recipes.length - 3}</p>}
          {where && where.usedIn > 0 && <p className="dbt-note">Нужен в рецептах: {where.usedIn.toLocaleString("ru-RU")}</p>}
        </div>
        <div className="dbt-box">
          <h5>Торговцы</h5>
          {!where ? <p className="dbt-note">Загружаю…</p> : where.vendors.length ? where.vendors.slice(0, 5).map((v) => (
            <div key={`${v.id}-${v.kind}`} className="dbt-li"><b>{v.name}</b><span>{VENDOR_KIND[v.kind] ?? v.kind}</span></div>
          )) : <p className="dbt-note">Не продаётся.</p>}
          {where && where.vendors.length > 5 && <p className="dbt-note">и ещё {where.vendors.length - 5}</p>}
        </div>
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
    <div className="dbt-card">
      <div className="item-card in-db dbt-entity" role="region" aria-label={row.name}>
        <div className="ic-title"><b className="ic-name">{row.name}</b></div>
        <div className="ic-top">
          {row.icon && <Icon name={row.icon} size={48} />}
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
          {part.icon ? <Icon name={part.icon} size={26} /> : <span className="icon blank dbt-part-blank" />}
          <span className={part.grade ? `g-${part.grade}` : ""}>{part.name || `ID ${part.id}`}</span>
          <b>×{part.count}</b>
        </li>
      ))}
    </ul>
  );
}

const STEP_VERB: Record<string, string> = { kill: "Убить", loot: "Добыть", gather: "Собрать", buy: "Купить", drop: "Добыть", craft: "Создать", after: "Сначала выполнить" };
const RACES: Record<string, string> = { pc_light: "Элийцы", pc_dark: "Асмодиане" };
const REWARD: Record<string, string> = { exp: "Опыт", gold: "Кинары", abyss: "Очки Бездны" };

/** A quest: its mark, the facts (category, race, level, place), who starts and ends it (on the map), the steps, the rewards. */
function QuestDetail({ all, row }: { all: NonNullable<Awaited<ReturnType<typeof pulseDb>>>; row: SectionRow }) {
  const [card, setCard] = useState<QuestCard | null | undefined>(undefined);
  const openMap = useOpenMap();
  useEffect(() => { let alive = true; setCard(undefined); questCard(all, row.id).then((c) => alive && setCard(c)); return () => { alive = false; }; }, [all, row.id]);
  const showNpc = (npc: QuestNpc) => {
    if (openMap && npc.map_id) openMap({ type: "npc", npc: npc.id, name: npc.name, map_id: npc.map_id, at: npc.at ?? undefined });
  };
  const npcLine = (label: string, npc: QuestNpc | null, fallbackName = "") => (
    <div className="dbt-npc">
      <span className="dbt-npc-label">{label}</span>
      {npc ? <>
        <b>{npc.name}</b>
        {npc.zone && <span className="dbt-npc-zone">{npc.zone}</span>}
        {npc.map_id && openMap && <button type="button" className="btn dbt-npc-map" onClick={() => showNpc(npc)}><IconPin />На карте</button>}
      </> : fallbackName ? <b>{fallbackName}</b> : <span className="dbt-npc-zone">в данных не указан</span>}
    </div>
  );
  const guide = card?.guide ?? null;
  const gold = card?.gold ?? row.icon === "quest:gold";
  const levels = card ? `${guide?.level ?? card.min_level ?? "?"}${card.max_level ? `–${card.max_level}` : ""}` : ""; // aidb's level first: the client's minimum can differ
  const classes = guide ? (guide.classes.length >= 14 ? "Все классы" : guide.classes.join(", ")) : "";
  return (
    <div className="dbt-card dbt-quest">
      <div className="item-card in-db dbt-entity" role="region" aria-label={row.name}>
        <div className="ic-title dbt-quest-title">
          <QuestIcon gold={gold} size={34} />
          <div className="dbt-quest-names"><b className={`ic-name ${gold ? "dbt-gold" : "dbt-blue"}`}>{row.name}</b>{guide?.name_en && <span>{guide.name_en}</span>}</div>
        </div>
        {card === undefined ? <div className="ic-text muted">Загружаю…</div> : !card ? <div className="ic-text muted">Задания нет в базе.</div> : <>
          <dl className="ic-pairs">
            <dt>Категория</dt><dd>{guide?.category || questLine(`${card.kind}|${card.zone}`)}</dd>
            {(guide?.race || card.races.length > 0) && <><dt>Раса</dt><dd>{guide?.race || (card.races.length > 1 ? "Обе" : RACES[card.races[0]] ?? card.races[0])}</dd></>}
            <dt>Уровень</dt><dd>{levels}{guide?.rec_level ? <span className="dbt-rec"> · рек. {guide.rec_level}</span> : null}</dd>
            {(guide?.zone || card.zone) && <><dt>Локация</dt><dd>{guide?.zone || card.zone}</dd></>}
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
              <li key={n.id}>{n.icon ? <Icon name={n.icon} size={22} /> : <span className="icon blank dbt-part-blank" />}<span className={n.grade ? `g-${n.grade}` : ""}>{n.name}</span><b>×{n.count}</b></li>))}</ul>
          </>}
          <hr className="ic-hr" />
          <div className="dbt-made-title">Прохождение</div>
          {guide?.steps.length ? <ol className="dbt-steps">{guide.steps.map((st, i) => <li key={i}>{st.text}</li>)}</ol>
            : card.steps.length ? <ol className="dbt-steps">
              {card.steps.map((step, i) => (
                <li key={i}>
                  <span className="dbt-step-verb">{STEP_VERB[step.do] ?? step.do}</span>
                  {step.do === "after" && <span>{(step.quests ?? []).map((q) => `«${q.name}»`).join(", ")}</span>}
                  {step.do === "craft" && <span>{PROFESSION[step.skill ?? ""] ?? "предмет ремеслом"}{step.level ? `, навык ${step.level}` : ""}</span>}
                  {step.item && <span className="dbt-step-item">
                    {step.item.icon && <Icon name={step.item.icon} size={22} />}
                    <span className={step.item.grade ? `g-${step.item.grade}` : ""}>{step.item.name}</span>
                    {step.count ? <b>×{step.count}</b> : null}
                  </span>}
                  {step.from && (step.from.length > 0 || (step.more ?? 0) > 0) && <span className="dbt-step-from">
                    {step.do === "buy" ? "у " : step.do === "kill" || step.do === "gather" ? "" : "с "}
                    {step.from.map((n) => n.name).join(", ")}
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
                ? <li key={i}>{r.item.icon ? <Icon name={r.item.icon} size={22} /> : <span className="icon blank dbt-part-blank" />}<span className={r.item.grade ? `g-${r.item.grade}` : ""}>{r.item.name}</span><b>{r.choice ? "на выбор · " : ""}×{r.amount}</b></li>
                : <li key={i}><span>{REWARD[r.type] ?? r.type}</span><b>{r.amount.toLocaleString("ru-RU")}</b></li>)}
              {card.rewards.every((r) => !r.item) && (guide?.choice ?? []).map((c) => (
                <li key={`c${c.id}`}>{c.icon ? <Icon name={c.icon} size={22} /> : <span className="icon blank dbt-part-blank" />}<span className={c.grade ? `g-${c.grade}` : ""}>{c.name}</span><b>на выбор · ×{c.count}</b></li>))}
              {guide?.title && <li><span>Титул</span><b className="dbt-title-reward">{guide.title}</b></li>}
            </ul>
          </>}
          <hr className="ic-hr" /><div className="ic-text muted">ID {row.id}{guide ? " · описание: aidb.ru" : ""}</div>
        </>}
      </div>
    </div>
  );
}
