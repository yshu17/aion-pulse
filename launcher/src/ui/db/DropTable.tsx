// «Добыча» of an item's card: who drops it as a table (NPC · level · zone · map) with a search, the zones as chips, the same
// names together and «Показать на карте» for a row or for all that is listed (core/db/itemDroppers.ts, task 34).
import { Fragment, useEffect, useState } from "react";

import { bestMap, dropperRows, dropperZones, filterDroppers, itemDroppers, mapPoints, zoneCounts, type Dropper, type DropSort } from "../../core/db/itemDroppers";
import type { All } from "../../core/db/npcPoints";
import { mapNames } from "../data";
import { IconPin, IconSearch } from "../icons";
import { zones } from "../map/mapData";
import { useOpenMap, useOpenRef } from "../map/placeLink";
import "./dropTable.css";

const SHORT = 8; // rows before «Показать всех», while nothing is searched or filtered
const RANK: Record<string, string> = { "Элитный": "элит.", "Героический": "героич." };
const mapName = (id: string) => zones[id]?.name ?? mapNames[id] ?? id;

export function DropTable({ all, itemId, itemName, total }: { all: All; itemId: number; itemName: string; total: number }) {
  const open = useOpenRef();
  const openMap = useOpenMap();
  const [list, setList] = useState<Dropper[] | null>(null);
  const [query, setQuery] = useState("");
  const [zone, setZone] = useState("");
  const [onlyMap, setOnlyMap] = useState(false);
  const [together, setTogether] = useState(true);
  const [sort, setSort] = useState<[DropSort, 1 | -1]>(["name", 1]);
  const [expanded, setExpanded] = useState(false);
  const [openRows, setOpenRows] = useState<string[]>([]);
  useEffect(() => {
    let alive = true;
    setList(null); setQuery(""); setZone(""); setExpanded(false); setOpenRows([]);
    const names = Object.fromEntries(Object.entries(mapNames).map(([id, name]) => [id, zones[id]?.name ?? name]));
    itemDroppers(all, itemId, names).then((got) => alive && setList(got)).catch(() => alive && setList([]));
    return () => { alive = false; };
  }, [all, itemId]);

  if (!list) return <div className="dbt-box"><h5>Добыча<em>{total.toLocaleString("ru-RU")}</em></h5><p className="dbt-note">Загружаю, кто роняет…</p></div>;

  const found = filterDroppers(list, { query, zone, onlyMap });
  const rows = dropperRows(found, together, sort[0], sort[1]);
  const cut = !expanded && !query && !zone && !onlyMap && rows.length > SHORT;
  const shown = cut ? rows.slice(0, SHORT) : rows;
  const onMap = found.filter((d) => d.points > 0).length;
  const showOnMap = async (who: Dropper[], name: string) => {
    const best = bestMap(who);
    if (!best || !openMap) return;
    const points = await mapPoints(all, best.npcs, best.map_id);
    // several NPCs go to the map under an id of their own: the map draws the points it is given
    openMap({ type: "npc", npc: who.length === 1 ? who[0].id : `drop:${itemId}`, name, map_id: best.map_id, points });
  };
  const pin = (who: Dropper[], name: string, count: number) => {
    const best = bestMap(who);
    const title = best ? `Показать на карте: ${mapName(best.map_id)}, точек ${best.points}${best.others ? ` (ещё локаций: ${best.others})` : ""}` : "Мест появления в базе нет";
    return <button type="button" className="drops-pin" disabled={!best || !openMap} title={title} aria-label={`${title}. ${name}`} onClick={() => showOnMap(who, name)}><IconPin />{count || "—"}</button>;
  };
  const head = (key: DropSort, label: string, cls: string) => (
    <button type="button" className={cls} aria-pressed={sort[0] === key} onClick={() => setSort(([k, d]) => [key, k === key ? (d === 1 ? -1 : 1) : 1])}>
      {label}{sort[0] === key ? (sort[1] === 1 ? " ▲" : " ▼") : ""}
    </button>
  );
  const name = (id: string, text: string) => (open
    ? <button type="button" className="drops-name" title={`${text}: открыть карточку NPC`} onClick={() => open({ kind: "npc", id, name: text })}>{text}</button>
    : <span className="drops-name">{text}</span>);

  return (
    <div className="dbt-box drops">
      <div className="drops-head">
        <h5>Добыча<em>{total.toLocaleString("ru-RU")}</em></h5>
        <button type="button" className="drops-all" disabled={!onMap || !openMap} title="Точки всех NPC из списка (на локации, где их больше всего)"
          onClick={() => showOnMap(found, `Кто роняет: ${itemName}`)}><IconPin />На карте: {onMap} NPC</button>
      </div>
      <div className="bst-search small"><IconSearch /><input className="field" placeholder="Найти NPC или локацию…" aria-label="Поиск по добыче" value={query} onChange={(e) => setQuery(e.target.value)} /></div>
      <div className="drops-checks">
        <label><input type="checkbox" checked={onlyMap} onChange={(e) => setOnlyMap(e.target.checked)} />Только с точками на карте</label>
        <label><input type="checkbox" checked={together} onChange={(e) => setTogether(e.target.checked)} />Одинаковые вместе</label>
      </div>
      <div className="drops-chips" role="group" aria-label="Локация">
        <button type="button" aria-pressed={!zone} onClick={() => setZone("")}>Все<b>{list.length}</b></button>
        {zoneCounts(list).map(([z, n]) => <button key={z} type="button" aria-pressed={zone === z} onClick={() => setZone(zone === z ? "" : z)}>{z}<b>{n}</b></button>)}
      </div>
      <div className={`drops-table${cut ? " short" : ""}`}>
        <div className="drops-row drops-th">{head("name", "NPC", "")}{head("level", "Ур.", "lv")}{head("zone", "Локация", "zn")}{head("points", "Карта", "pn")}</div>
        {shown.map((r) => {
          const opened = openRows.includes(r.key);
          const place = r.zones.join(", ");
          return (
            <Fragment key={r.key}>
              <div className="drops-row">
                <span className="nm">{name(r.id, r.name)}{RANK[r.rank] && <em>{RANK[r.rank]}</em>}
                  {r.members.length > 1 && <button type="button" className="drops-many" aria-expanded={opened} title={`${r.members.length} NPC с этим именем: раскрыть`}
                    onClick={() => setOpenRows((o) => (opened ? o.filter((k) => k !== r.key) : [...o, r.key]))}>×{r.members.length}</button>}</span>
                <span className="lv">{r.low === r.high ? r.low || "—" : `${r.low}–${r.high}`}</span>
                <span className={`zn${place ? "" : " none"}`} title={place}>{place || "неизвестно"}</span>
                <span className="pn">{pin(r.members, r.name, r.points)}</span>
              </div>
              {opened && r.members.map((m) => (
                <div key={m.id} className="drops-row sub">
                  <span className="nm">{name(m.id, m.name)}<small>ID {m.id}</small></span>
                  <span className="lv">{m.level || "—"}</span>
                  <span className="zn">{dropperZones(m).join(", ")}</span>
                  <span className="pn">{pin([m], m.name, m.points)}</span>
                </div>
              ))}
            </Fragment>
          );
        })}
        {!shown.length && <p className="dbt-note drops-none">Ничего не нашлось. Сбрось локацию или попробуй часть имени.</p>}
      </div>
      <div className="drops-foot">
        <span>{together ? `Строк: ${rows.length} (NPC: ${found.length})` : `NPC: ${found.length}`}</span>
        {cut ? <button type="button" className="dbt-more-link" onClick={() => setExpanded(true)}>Показать всех ({rows.length.toLocaleString("ru-RU")})</button>
          : expanded && rows.length > SHORT && <button type="button" className="dbt-more-link" onClick={() => setExpanded(false)}>Свернуть</button>}
      </div>
    </div>
  );
}
