// The «NPC / Бестиарий» tab: the bestiary's NPCs and monsters (data/bestiary/npcs.sqlite) — a search with the class
// chips and the level, the found list on the left, the chosen NPC's card on the right (goods or drops, its zone on a small
// map, «Показать на карте»). The data is read by core/bestiary/store.ts; what is shown of it by core/bestiary/view.ts.
import { memo, useEffect, useMemo, useState } from "react";

import { dropsNote, filterDrops, filterStock, RARITY, SORTS, stockNote, type Detail } from "../../core/bestiary/card";
import type { BestiaryStore, Row } from "../../core/bestiary/store";
import { iconPath, LEVELS, levelRange, mainPlace, RANK_CHIPS, rarityClass, roleLabel, rowSubtitle } from "../../core/bestiary/view";
import { toImage, type Zone } from "../../core/map/zones";
import { IconCart, IconClose, IconNavigate, IconPin, IconSearch, IconShield, IconUser } from "../icons";
import { loadSpawns, pictureUrl, PLACE_ICON, zones } from "../map/mapData";
import { useOpenMap } from "../map/placeLink";
import { bestiaryIcon, openBestiary } from "./bestiaryDb";
import "./bestiary.css";

const PAGE = 150; // rows per search; «Показать ещё» adds the next ones
const TYPE_MS = 140; // the list searches this long after the last change: fast typing runs one search
const GOODS_SHOWN = 120; // the card draws at most this many goods (a merchant may sell hundreds): the search narrows them

/** A picture of data/bestiary/icons, or an empty tile while it loads or when it is missing. */
function Pic({ path, className }: { path: string | null | undefined; className: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    setUrl(null);
    bestiaryIcon(iconPath(path)).then((got) => { if (alive) setUrl(got); });
    return () => { alive = false; };
  }, [path]);
  return url ? <img className={className} src={url} alt="" draggable={false} /> : <span className={`${className} blank`} aria-hidden="true" />;
}

function Banner() {
  return (
    <header className="bst-banner">
      <h1>Бестиарий</h1>
      <p>Каталог NPC Aion: боссы, элитные и уникальные существа</p>
    </header>
  );
}

export function BestiaryTab() {
  const [store, setStore] = useState<BestiaryStore | null | undefined>(undefined); // undefined: still opening
  useEffect(() => { openBestiary().then(setStore); }, []);
  if (store === undefined) return <main className="bst"><Banner /><div className="bst-state" role="status">Загружаю базу бестиария…</div></main>;
  if (store === null) {
    return <main className="bst"><Banner /><div className="bst-state" role="status">База бестиария не найдена: нет папки data/bestiary.</div></main>;
  }
  return <Bestiary store={store} />;
}

function Bestiary({ store }: { store: BestiaryStore }) {
  const [query, setQuery] = useState("");
  const [rank, setRank] = useState("");
  const [level, setLevel] = useState(LEVELS[0]);
  const [order, setOrder] = useState("level_desc");
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const options = useMemo(() => ({ text: query, rank, order, limit: PAGE, ...levelRange(level) }), [query, rank, order, level]);
  useEffect(() => {
    const timer = setTimeout(() => {
      const [found, count] = store.search(options);
      setRows(found);
      setTotal(count);
      setSelected((now) => (now && found.some((r) => String(r.id) === now) ? now : found.length ? String(found[0].id) : null));
    }, TYPE_MS);
    return () => clearTimeout(timer);
  }, [store, options]);
  const more = () => {
    const [next] = store.search({ ...options, offset: rows.length });
    setRows((list) => [...list, ...next]);
  };
  const detail = useMemo(() => (selected ? store.detail(selected) : null), [store, selected]);

  return (
    <main className="bst">
      <Banner />
      <div className="bst-bar">
        <div className="bst-search">
          <IconSearch />
          <input className="field" placeholder="Поиск по имени NPC, луту, локации…" value={query} aria-label="Поиск NPC"
            onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") setQuery(""); }} />
          {query && <button className="x" aria-label="Очистить поиск" onClick={() => setQuery("")}><IconClose /></button>}
        </div>
        <div className="bst-chips" role="radiogroup" aria-label="Класс">
          {RANK_CHIPS.map(([label, value]) => (
            <button key={label} type="button" role="radio" aria-checked={rank === value} className={`bst-chip${rank === value ? " on" : ""}`}
              onClick={() => setRank(value)}>{label}</button>
          ))}
        </div>
        <span className="spacer" />
        <label className="bst-level">
          <span>Уровень</span>
          <select className="field" value={level} onChange={(e) => setLevel(e.target.value)}>
            {LEVELS.map((choice) => <option key={choice}>{choice}</option>)}
          </select>
        </label>
      </div>
      <div className="bst-body">
        <section className="bst-list" aria-label="Найденные NPC">
          <div className="bst-list-head">
            <span>Найдено: <b>{total}</b> NPC</span>
            <label className="bst-sort">
              <span>Сортировка:</span>
              <select className="field" value={order} onChange={(e) => setOrder(e.target.value)}>
                {Object.entries(SORTS).map(([label, value]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
          </div>
          <Rows rows={rows} selected={selected} onSelect={setSelected} />
          {rows.length < total && <button className="btn bst-more" onClick={more}>Показать ещё ({total - rows.length})</button>}
          {!rows.length && <div className="bst-empty">Никого не нашлось: проверь слово или сними фильтр класса и уровня.</div>}
        </section>
        <section className="bst-detail" aria-label="Карточка NPC">
          {detail ? <Card key={String(detail.id)} detail={detail} /> : <div className="bst-empty">Выбери NPC в списке.</div>}
        </section>
      </div>
    </main>
  );
}

/** The list rows; memoized, so typing in the search box does not draw them again. */
const Rows = memo(function Rows({ rows, selected, onSelect }: { rows: Row[]; selected: string | null; onSelect(id: string): void }) {
  return (
    <ul className="bst-rows">
      {rows.map((row) => {
        const id = String(row.id);
        return (
          <li key={id}>
            <button className={`bst-row${id === selected ? " on" : ""}`} aria-current={id === selected} onClick={() => onSelect(id)}>
              <Pic path={row.icon_asset} className="bst-row-pic" />
              <span className="bst-row-text"><b>{row.name}</b><span>{rowSubtitle(row)}</span></span>
            </button>
          </li>
        );
      })}
    </ul>
  );
});

function Card({ detail }: { detail: Detail }) {
  const openMap = useOpenMap();
  const [q, setQ] = useState("");
  const place = mainPlace(detail);
  const zone = place ? zones[place.map_id] : undefined;
  const role = roleLabel(detail.role);
  const sells = Array.isArray(detail.stock) && detail.stock.length > 0;
  const goods = sells ? filterStock(detail, q) : filterDrops(detail, q);
  const total = (sells ? detail.stock : detail.drops ?? []).length;
  const note = sells ? stockNote(goods.length, total) : dropsNote(goods.length, detail);
  const where = zone?.name ?? (detail.zone_names as string | undefined) ?? "";
  const service = (detail.description as string | undefined) || (detail.category === "monster" ? "" : role);
  const showOnMap = async () => {
    if (!place || !openMap) return;
    const id = String(detail.id);
    const spawns = await loadSpawns();
    if (spawns.points(id, place.map_id).length) openMap({ type: "npc", npc: id, name: detail.name, map_id: place.map_id, at: [place.gx, place.gy] });
    else openMap({ type: "place", map_id: place.map_id, x: place.gx, y: place.gy, label: detail.name, note: "", nick: "", time: "", text: "" });
  };

  return (
    <div className="bst-card">
      <div className="bst-top">
        <div className="bst-portrait">
          <Pic path={detail.icon_asset} className="bst-portrait-pic" />
          {(role || detail.kind) && <span className="bst-tag">{role || detail.kind}</span>}
        </div>
        <div className="bst-info">
          <h2>{detail.name}</h2>
          {detail.title && <p className="bst-title">{detail.title}</p>}
          <div className="bst-badges">
            {detail.level !== "" && detail.level !== null && detail.level !== undefined && <span className="bst-badge level">Ур. {detail.level}</span>}
            {role && <span className="bst-badge role"><IconCart />{role}</span>}
            {detail.rank && <span className="bst-badge"><IconUser />{detail.rank}</span>}
          </div>
          <dl className="bst-facts">
            <div><dt><IconShield />Сторона</dt><dd>{detail.faction || detail.race || "Не указана"}</dd></div>
            <div><dt><IconPin />Локация</dt><dd>{where || "Не указана"}{place && place.count > 1 ? ` · точек ${place.count}` : ""}</dd></div>
            {service && <div><dt><IconCart />Услуги</dt><dd>{service}</dd></div>}
            {!service && detail.kind && <div><dt><IconUser />Вид</dt><dd>{detail.kind}</dd></div>}
          </dl>
        </div>
        {zone && place ? <MiniMap zone={zone} gx={place.gx} gy={place.gy} /> : <div className="bst-map none">Места на карте нет</div>}
      </div>

      <div className="bst-goods-head">
        <h3>{sells ? "Товары" : "Добыча"}</h3>
        <div className="bst-search small">
          <IconSearch />
          <input className="field" placeholder={sells ? "Поиск по товарам в ассортименте…" : "Поиск по добыче…"} value={q}
            aria-label={sells ? "Поиск по товарам" : "Поиск по добыче"} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      <ul className="bst-goods">
        {goods.slice(0, GOODS_SHOWN).map(([i, item]) => (
          <li key={i} className="bst-good">
            <Pic path={item.icon_asset ?? item.icon} className="bst-good-pic" />
            <span className="bst-good-text">
              <b className={rarityClass(item.rarity)}>{item.name}</b>
              <span>{item.group || RARITY[item.rarity as string] || ""}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="bst-note">{note}</p>
      <div className="bst-actions">
        <button className="btn primary bst-go" disabled={!place || !openMap} onClick={showOnMap}><IconPin />Показать на карте</button>
      </div>
    </div>
  );
}

/** The NPC's zone around its point, the place marked in the middle, as the «Место из чата» card of the map. */
function MiniMap({ zone, gx, gy }: { zone: Zone; gx: number; gy: number }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => { let alive = true; pictureUrl(zone.file).then((got) => { if (alive) setUrl(got); }); return () => { alive = false; }; }, [zone.file]);
  const [x, y] = toImage(zone, gx, gy);
  return (
    <div className="bst-map" aria-label={`На карте: ${zone.name}`}>
      {url && <img className="pic" src={url} alt="" draggable={false} style={{ width: zone.size, height: zone.size, left: `calc(50% - ${x}px)`, top: `calc(50% - ${y}px)` }} />}
      {PLACE_ICON ? <img className="mark" src={PLACE_ICON} alt="" /> : <span className="mark dot"><IconNavigate /></span>}
      <span className="bst-map-name">{zone.name}</span>
    </div>
  );
}
