// The «NPC / Бестиарий» tab: the bestiary's NPCs and monsters (data/bestiary/npcs.sqlite) — a search with the class
// chips and the level, the found list on the left, the chosen NPC's card on the right as Pulse shows it: the HP artwork,
// the numbers (HP, DP, abyss rank, XP, points…), and the tabs «Добыча», «Локации» and «Товары». The data is read by
// core/bestiary/store.ts in a worker (bestiaryDb.ts): the tab is drawn at once with placeholders, the search box works from
// the first moment, and the answers come in when ready; what is shown of them by core/bestiary/card.ts and view.ts.
import { memo, startTransition, useEffect, useMemo, useRef, useState } from "react";

import { dropsNote, filterDrops, filterStock, overviewText, placeCounts, RARITY, SORTS, stockNote, type Detail } from "../../core/bestiary/card";
import { statText } from "../../core/bestiary/labels";
import type { Row } from "../../core/bestiary/store";
import { hpFrame, iconPath, LEVELS, levelRange, mainPlace, placeAt, rankTier, RANK_CHIPS, rarityClass, roleLabel, rowSubtitle, statGroups } from "../../core/bestiary/view";
import { toImage, type Zone } from "../../core/map/zones";
import { mapNames } from "../data";
import { IconClose, IconNavigate, IconPin, IconSearch } from "../icons";
import { loadSpawns, pictureUrl, PLACE_ICON, zones } from "../map/mapData";
import { useOpenMap } from "../map/placeLink";
import { bestiaryIcon, openBestiary, type BestiaryClient } from "./bestiaryDb";
import "./bestiary.css";

const PAGE = 150; // rows per search; «Показать ещё» adds the next ones
const TYPE_MS = 140; // the list searches this long after the last change: fast typing runs one search
const GOODS_SHOWN = 120; // the card draws at most this many goods or drops (a merchant may sell hundreds): the search narrows them

/** A picture of data/bestiary/icons, or an empty tile while it loads or when it is missing. */
function Pic({ path, className }: { path: string | null | undefined; className: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    setUrl(null);
    bestiaryIcon(iconPath(path)).then((got) => { if (alive) setUrl(got); });
    return () => { alive = false; };
  }, [path]);
  return url ? <img className={className} src={url} alt="" draggable={false} decoding="async" loading="lazy" /> : <span className={`${className} blank`} aria-hidden="true" />;
}

export function BestiaryTab() {
  const [client, setClient] = useState<BestiaryClient | null | undefined>(undefined); // undefined: still opening
  useEffect(() => { openBestiary().then(setClient); }, []);
  return <Bestiary client={client} />;
}

function Bestiary({ client }: { client: BestiaryClient | null | undefined }) {
  const [query, setQuery] = useState("");
  const [rank, setRank] = useState("");
  const [level, setLevel] = useState(LEVELS[0]);
  const [order, setOrder] = useState("level_desc");
  const [rows, setRows] = useState<Row[]>([]);
  const [total, setTotal] = useState(0);
  const [searching, setSearching] = useState(true); // the first answer has not come yet
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<Row | null>(null);
  const asked = useRef(0); // the newest search: an older answer arriving late is dropped
  const options = useMemo(() => ({ text: query, rank, order, limit: PAGE, ...levelRange(level) }), [query, rank, order, level]);
  useEffect(() => {
    if (!client) return;
    const seq = ++asked.current;
    const timer = setTimeout(() => {
      client.search(options).then((answer) => {
        if (!answer || seq !== asked.current) return;
        const [found, count] = answer;
        startTransition(() => { // the list redraws when the page is free: the search box stays quick
          setRows(found);
          setTotal(count);
          setSearching(false);
          setSelected((now) => (now && found.some((r) => String(r.id) === now) ? now : found.length ? String(found[0].id) : null));
        });
      }).catch(() => setSearching(false));
    }, TYPE_MS);
    return () => clearTimeout(timer);
  }, [client, options]);
  const more = () => {
    client?.search({ ...options, offset: rows.length }).then((answer) => {
      if (answer) startTransition(() => setRows((list) => [...list, ...answer[0]]));
    });
  };
  useEffect(() => {
    if (!client || !selected) { setDetail(null); return; }
    let alive = true;
    client.detail(selected).then((got) => { if (alive) startTransition(() => setDetail(got)); }).catch(() => {});
    return () => { alive = false; };
  }, [client, selected]);
  const loading = client === undefined || (client !== null && searching);

  return (
    <main className="bst">
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
            <span>Найдено: <b>{loading ? "…" : total}</b> NPC</span>
            <label className="bst-sort">
              <span>Сортировка:</span>
              <select className="field" value={order} onChange={(e) => setOrder(e.target.value)}>
                {Object.entries(SORTS).map(([label, value]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
          </div>
          {loading ? <RowsSkeleton /> : <Rows rows={rows} selected={selected} onSelect={setSelected} />}
          {!loading && rows.length < total && <button className="btn bst-more" onClick={more}>Показать ещё ({total - rows.length})</button>}
          {client === null && <div className="bst-empty">База бестиария не найдена: нет папки data/bestiary.</div>}
          {!loading && client && !rows.length && <div className="bst-empty">Никого не нашлось: проверь слово или сними фильтр класса и уровня.</div>}
        </section>
        <section className="bst-detail" aria-label="Карточка NPC">
          {detail && client ? <Card key={String(detail.id)} client={client} detail={detail} />
            : loading || (selected && client) ? <CardSkeleton /> : <div className="bst-empty">Выбери NPC в списке.</div>}
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
            <button className={`bst-row r${rankTier(row.rank)}${id === selected ? " on" : ""}`} aria-current={id === selected} onClick={() => onSelect(id)}>
              <Pic path={row.icon_asset} className="bst-row-pic" />
              <span className="bst-row-text"><b>{row.name}</b><span>{rowSubtitle(row)}</span></span>
            </button>
          </li>
        );
      })}
    </ul>
  );
});

/** The list while the base opens or the first search runs: grey rows in the list's own shape. */
function RowsSkeleton() {
  return (
    <ul className="bst-rows" aria-busy="true" aria-label="Загружаю список">
      {Array.from({ length: 10 }, (_, i) => (
        <li key={i} className="bst-row skel"><span className="bst-skel circle" /><span className="bst-row-text"><span className="bst-skel line" /><span className="bst-skel line short" /></span></li>
      ))}
    </ul>
  );
}

/** The card while its data comes: the hero, the four tiles and the facts as grey blocks. */
function CardSkeleton() {
  return (
    <div className="bst-card" aria-busy="true" aria-label="Загружаю карточку">
      <div className="bst-hero"><div className="bst-hero-main"><span className="bst-skel line short" /><span className="bst-skel line title" /><span className="bst-skel bar" /></div><span className="bst-skel map" /></div>
      <div className="bst-tiles">{Array.from({ length: 4 }, (_, i) => <span key={i} className="bst-skel tile" />)}</div>
      <span className="bst-skel line" /><span className="bst-skel line" /><span className="bst-skel line short" />
    </div>
  );
}

type TabName = "drops" | "places" | "stock";

const Card = memo(function Card({ client, detail }: { client: BestiaryClient; detail: Detail }) {
  const openMap = useOpenMap();
  const sells = Array.isArray(detail.stock) && detail.stock.length > 0;
  const [tab, setTab] = useState<TabName>(sells ? "stock" : "drops");
  const [zone, setZone] = useState<string | null>(() => mainPlace(detail)?.map_id ?? null); // the zone the map and the button show
  const place = zone ? placeAt(detail, zone) : null;
  const picture = place ? zones[place.map_id] : undefined;
  const text = overviewText(detail);
  const side = detail.faction === "Другие" ? detail.race : detail.faction;
  const role = roleLabel(detail.role);
  const showOnMap = async () => {
    if (!place || !openMap) return;
    const id = String(detail.id);
    const spawns = await loadSpawns();
    if (spawns.points(id, place.map_id).length) openMap({ type: "npc", npc: id, name: detail.name, map_id: place.map_id, at: [place.gx, place.gy] });
    else openMap({ type: "place", map_id: place.map_id, x: place.gx, y: place.gy, label: detail.name, note: "", nick: "", time: "", text: "" });
  };

  const { key, rest } = statGroups(detail);
  const dropsCount = (detail.drops ?? []).length;
  const placesCount = new Set((detail.points ?? []).map((p: Detail) => String(p.map_id))).size;

  return (
    <div className={`bst-card r${rankTier(detail.rank)}`}>
      <section className="bst-hero">
        <div className="bst-hero-main">
          <div className="bst-pills">
            {detail.kind && <span className="bst-pill kind">{detail.kind}</span>}
            {side && <span className="bst-pill side">{side}</span>}
            {detail.rank && <span className="bst-pill rank">{detail.rank}</span>}
            {role && role !== detail.kind && <span className="bst-pill kind">{role}</span>}
          </div>
          <h2>{detail.name}</h2>
          {detail.title && <p className="bst-title">{detail.title}</p>}
          <HpBar detail={detail} />
        </div>
        {picture && place ? <MiniMap zone={picture} gx={place.gx} gy={place.gy} /> : <div className="bst-map none">Места на карте нет</div>}
      </section>

      {text && <p className="bst-desc">{text}</p>}
      {key.length > 0 && (
        <div className="bst-tiles">
          {key.map(([name, value]) => <div key={name} className="bst-tile"><span>{name}</span><b>{value}</b></div>)}
        </div>
      )}
      {rest.length > 0 && (
        <dl className="bst-facts">
          {rest.map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}
        </dl>
      )}
      {!key.length && <p className="bst-note">Числовой профиль (ХП, опыт, ДП) для этого NPC не загружен.</p>}

      <div className="bst-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "drops"} className={tab === "drops" ? "on" : ""} onClick={() => setTab("drops")}>Добыча<i>{dropsCount}</i></button>
        <button role="tab" aria-selected={tab === "places"} className={tab === "places" ? "on" : ""} onClick={() => setTab("places")}>Локации<i>{placesCount}</i></button>
        {sells && <button role="tab" aria-selected={tab === "stock"} className={tab === "stock" ? "on" : ""} onClick={() => setTab("stock")}>Товары<i>{detail.stock.length}</i></button>}
      </div>
      {tab === "places" ? <Places client={client} detail={detail} zone={zone} onZone={setZone} /> : <Goods key={tab} detail={detail} kind={tab} />}

      <div className="bst-foot">
        <span className="bst-note">{detail.kb_status === "loaded" ? "Данные KB + файлы клиента" : "Данные клиента; подробный профиль KB не загружен"}</span>
        <button className="btn primary bst-go" disabled={!place || !openMap} onClick={showOnMap}><IconPin />Показать на карте</button>
      </div>
    </div>
  );
});

/** The HP artwork as Pulse draws it: the rank's bar of the sprite, the emblem in a circle, the level at its left. */
function HpBar({ detail }: { detail: Detail }) {
  const bar = hpFrame(detail);
  const [sprite, setSprite] = useState<string | null>(null);
  useEffect(() => { let alive = true; bestiaryIcon("npc/hp-bars.png").then((got) => { if (alive) setSprite(got); }); return () => { alive = false; }; }, []);
  const level = detail.level || "?";
  if (!bar) return <p className="bst-hp-none">Уровень {detail.level || "—"} · Ранг не указан</p>;
  const [x0, y0, x1, y1] = bar.frame;
  return (
    <div className="bst-hp-row">
      <div className="bst-hp" role="img" aria-label={`Уровень ${level}`} style={{ width: x1 - x0, height: y1 - y0,
        backgroundImage: sprite ? `url(${sprite})` : undefined, backgroundPosition: `${-x0}px ${-y0}px` }}>
        <span className="bst-hp-icon" style={{ left: bar.iconLeft, top: bar.iconTop }}><Pic path={detail.icon_asset || "ui/monster.png"} className="bst-hp-pic" /></span>
        <span className="bst-hp-level" style={{ left: bar.levelLeft, top: bar.levelTop }}>{level}</span>
      </div>
      <div className="bst-hp-text">
        <b>Уровень {detail.level || "—"}</b>
        <span>Макс. ХП: {statText(detail.stats?.["Макс. ХП"] ?? "—")}</span>
      </div>
    </div>
  );
}

/** The NPC's drops («Добыча») or goods («Товары») with the search box and a note under. */
function Goods({ detail, kind }: { detail: Detail; kind: "drops" | "stock" }) {
  const [q, setQ] = useState(() => "");
  const sells = kind === "stock";
  const list = sells ? filterStock(detail, q) : filterDrops(detail, q);
  const total = ((sells ? detail.stock : detail.drops) ?? []).length;
  const note = sells ? stockNote(list.length, total) : dropsNote(list.length, detail);
  return (
    <div className="bst-panel" role="tabpanel">
      <div className="bst-search small">
        <IconSearch />
        <input className="field" placeholder={sells ? "Поиск по товарам в ассортименте…" : "Поиск по добыче…"} value={q}
          aria-label={sells ? "Поиск по товарам" : "Поиск по добыче"} onChange={(e) => setQ(e.target.value)} />
      </div>
      <ul className="bst-goods">
        {list.slice(0, GOODS_SHOWN).map(([i, item]) => (
          <li key={i} className={`bst-good ${rarityClass(item.rarity)}`}>
            <Pic path={item.icon_asset ?? item.icon} className="bst-good-pic" />
            <span className="bst-good-text">
              <b>{item.name}</b>
              <span>{[item.group, sells ? item.trade_mode : RARITY[item.rarity as string]].filter(Boolean).join(" · ")}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="bst-note">{note}</p>
    </div>
  );
}

/** The zones the NPC stands in with their points, and the approximate areas under each; a zone chosen here is shown on the map. */
function Places({ client, detail, zone, onZone }: { client: BestiaryClient; detail: Detail; zone: string | null; onZone(id: string): void }) {
  const ids = [...new Set<string>((detail.points ?? []).map((p: Detail) => String(p.map_id)))];
  const names = Object.fromEntries(ids.map((id) => [id, zones[id]?.name ?? mapNames[id] ?? id]));
  const counts = placeCounts(detail, names);
  const [areas, setAreas] = useState<Row[]>([]);
  useEffect(() => {
    let alive = true;
    client.areas(String(detail.id)).then((got) => { if (alive) setAreas(got); }).catch(() => {});
    return () => { alive = false; };
  }, [client, detail.id]);
  if (!counts.length) {
    return <div className="bst-panel" role="tabpanel"><p className="bst-note">Точки появления в файлах клиента не найдены.</p></div>;
  }
  return (
    <div className="bst-panel" role="tabpanel">
      <ul className="bst-places">
        {counts.map(([id, count]) => (
          <li key={id}>
            <button className={`bst-place${id === zone ? " on" : ""}`} aria-current={id === zone} onClick={() => onZone(id)}>
              <IconPin /><span>{names[id]}</span><b>{count}</b>
            </button>
            {areas.filter((a) => String(a.map_id) === id).map((a) => {
              const named = (a.names as string[]).filter((n) => !n.includes("�"));
              return <div key={a.area_id} className="bst-area"><span>≈ {named.length ? named.slice(0, 2).join(", ") : "Область появления"}</span><b>{a.point_count}</b></div>;
            })}
          </li>
        ))}
      </ul>
      <p className="bst-note">Области приблизительны; точки взяты из файлов клиента.</p>
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
