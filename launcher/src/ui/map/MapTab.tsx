// The «Карта» tab: a zone of Aion with its area names and points (teleporters, kisks, merchants, fortresses …) drawn
// with the game's own map icons, as Pulse's map (watcher/mapview.py). The wheel zooms to the mouse, dragging moves the
// map, a double click zooms in. A place link from the chat opens here as a blue cross; the right panel shows it (or
// the picked point) and what is near it. The rules of the view live in core/map/view.ts.
import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { normalize } from "../../core/chat/matcher";
import { cluster, Poi } from "../../core/map/poi";
import {
  centreOn, clampView, fitView, fitZoom, gameAt, iconSize, labelLevels, MAX_ZOOM, nearby, Near, shownTypes, toScreen,
  View, ZOOM_STEP, zonesOfSide, zoomAt, BIG_TYPES, ICON_SCALE,
} from "../../core/map/view";
import { FILTER_GROUPS, SIDES, toImage, Zone } from "../../core/map/zones";
import { metresText } from "../../core/text";
import { Glide } from "../fx";
import { IconChevron, IconClose, IconFilter, IconFit, IconMessage, IconMinus, IconNavigate, IconPlus, IconSearch, IconTarget } from "../icons";
import type { Boot } from "../useBoot";
import { pictureUrl, PLACE_ICON, poi, typeIcon, zones } from "./mapData";
import type { ChatPlace } from "./placeLink";
import "./map.css";

const DEFAULT_ZONE = "220070000"; // Келькмарос
const SPLIT_ZOOM = (MAX_ZOOM / ZOOM_STEP) * 0.999; // the last two zoom levels: every point its own icon, no counts
const PLACE_ICON_PX = 34; // the blue cross of the chat's place, as on the game's map
const FLY_MS = 260;
const FILTER_ICON: Record<string, string> = { rifts: "tunnel" }; // the group's icon in «Фильтры»: the Silentera tunnel for the rifts
const ZOOM_MS = 170;

type Selected = { kind: "poi"; poi: Poi } | { kind: "area"; x: number; y: number; text: string } | null;
type Match = { kind: "poi"; poi: Poi } | { kind: "area"; x: number; y: number; text: string };

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
const ease = (t: number) => 1 - (1 - t) ** 3;

export function MapTab({ boot, place, onPlaceCleared }: { boot: Boot; place: (ChatPlace & { n: number }) | null; onPlaceCleared(): void }) {
  const cfg = boot.config;
  const [side, setSide] = useState(cfg.map_side in SIDES ? cfg.map_side : "dark");
  const [hidden, setHidden] = useState<string[]>(() => [...cfg.map_hidden.filter((g) => g in FILTER_GROUPS), ...(cfg.map_quests ? [] : ["quests"])]);
  const types = useMemo(() => shownTypes(poi, hidden), [hidden]);
  const [zoneId, setZoneId] = useState(() => place?.map_id ?? (DEFAULT_ZONE in zones ? DEFAULT_ZONE : Object.keys(zones)[0]));
  const zone: Zone | undefined = zones[zoneId];
  const [layer, setLayer] = useState<number | null>(zone?.layers[0]?.[0] ?? null);
  const [selected, setSelected] = useState<Selected>(null);
  const [shownPlace, setShownPlace] = useState<ChatPlace | null>(place);
  const motion = !(cfg.reduce_motion || reducedMotion());

  // --- the picture and the view ---------------------------------------------------------------------------------
  const box = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    measure();
    return () => observer.disconnect();
  }, []);
  const [view, setView] = useState<View | null>(null);
  const viewRef = useRef<View | null>(null);
  viewRef.current = view;
  const frame = useRef(0);
  const stop = () => { cancelAnimationFrame(frame.current); frame.current = 0; };
  /** Move the view along `at(t)` (t 0…1) over `ms`; at once without motion. */
  const animate = useCallback((at: (t: number) => View, ms: number) => {
    stop();
    if (!motion || ms <= 0) { setView(at(1)); return; }
    const start = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      setView(at(ease(t)));
      frame.current = t < 1 ? requestAnimationFrame(step) : 0;
    };
    frame.current = requestAnimationFrame(step);
  }, [motion]);
  useEffect(() => stop, []);

  const [picture, setPicture] = useState<string | null>(null);
  const [pictureMissing, setPictureMissing] = useState(false);
  const file = zone ? (zone.layers.find(([id]) => id === layer)?.[2] ?? zone.file) : null;
  useEffect(() => {
    if (!file) return;
    let alive = true;
    setPicture(null);
    setPictureMissing(false);
    pictureUrl(file).then((url) => { if (alive) { setPicture(url); setPictureMissing(url === null); } });
    return () => { alive = false; };
  }, [file]);

  // a new zone or the first size: the whole zone; a new size: kept on screen, never smaller than the fit
  const fittedZone = useRef<string | null>(null);
  useLayoutEffect(() => {
    if (!zone || !size || !size.w || !size.h) return;
    if (fittedZone.current !== zone.map_id) {
      fittedZone.current = zone.map_id;
      stop();
      setView(fitView(zone, size.w, size.h));
      return;
    }
    const v = viewRef.current;
    if (v) setView(clampView({ ...v, zoom: Math.max(v.zoom, fitZoom(zone, size.w, size.h)) }, zone, size.w, size.h));
  }, [zone, size]);

  const flyTo = useCallback((ix: number, iy: number, zoom?: number) => {
    const from = viewRef.current;
    if (!zone || !size || !from) return;
    const target = centreOn({ ...from, zoom: Math.max(fitZoom(zone, size.w, size.h), Math.min(MAX_ZOOM, zoom ?? from.zoom)) }, ix, iy, zone, size.w, size.h);
    animate((t) => ({ zoom: from.zoom * (target.zoom / from.zoom) ** t, left: from.left + (target.left - from.left) * t,
      top: from.top + (target.top - from.top) * t }), FLY_MS);
  }, [zone, size, animate]);

  // a place from the chat: its zone (and side), the map flies to it close enough to see the area
  const pendingPlace = useRef<ChatPlace | null>(null);
  useEffect(() => {
    if (!place) return;
    setShownPlace(place);
    setSelected(null);
    const target = zones[place.map_id];
    if (!target) return;
    if (target.side && target.side !== side) setSide(target.side);
    if (place.map_id !== zoneId) {
      setZoneId(place.map_id);
      setLayer(target.layers[0]?.[0] ?? null);
    }
    pendingPlace.current = place;
  }, [place?.n]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const p = pendingPlace.current;
    if (!p || !zone || p.map_id !== zone.map_id || !size || !view || fittedZone.current !== zone.map_id) return;
    pendingPlace.current = null;
    const [ix, iy] = toImage(zone, p.x, p.y);
    flyTo(ix, iy, Math.max(view.zoom, fitZoom(zone, size.w, size.h) * 2));
  });

  // --- the mouse: drag, wheel, double click --------------------------------------------------------------------
  const drag = useRef<{ x: number; y: number; view: View; moved: boolean } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [mouse, setMouse] = useState<[number, number] | null>(null);
  const local = (e: { clientX: number; clientY: number }) => {
    const r = box.current!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top] as [number, number];
  };
  const onPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0 || !view) return;
    stop();
    drag.current = { x: e.clientX, y: e.clientY, view, moved: false };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (zone && view) setMouse(gameAt(view, zone, ...local(e)));
    const d = drag.current;
    if (!d || !zone || !size) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (!d.moved && Math.abs(dx) < 4 && Math.abs(dy) < 4) return;
    if (!d.moved) { d.moved = true; setDragging(true); }
    setView(clampView({ zoom: d.view.zoom, left: d.view.left - dx / d.view.zoom, top: d.view.top - dy / d.view.zoom }, zone, size.w, size.h));
  };
  const onPointerUp = () => {
    setTimeout(() => { drag.current = null; }, 0); // a point's click comes after this: it must still see the drag
    setDragging(false);
  };
  const zoomTarget = useRef<number | null>(null);
  const zoomBy = useCallback((factor: number, sx: number, sy: number) => {
    const from = viewRef.current;
    if (!zone || !size || !from) return;
    const base = frame.current && zoomTarget.current ? zoomTarget.current : from.zoom; // wheel clicks in a row add up
    const z = Math.max(fitZoom(zone, size.w, size.h), Math.min(MAX_ZOOM, base * factor));
    zoomTarget.current = z;
    animate((t) => zoomAt(from, from.zoom * (z / from.zoom) ** t, sx, sy, zone, size.w, size.h), ZOOM_MS);
  }, [zone, size, animate]);
  useEffect(() => { // passive: false, so the page does not scroll under the map
    const el = box.current;
    if (!el) return;
    const wheel = (e: WheelEvent) => {
      e.preventDefault();
      if (e.deltaY === 0) return;
      const r = el.getBoundingClientRect();
      zoomBy(e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP, e.clientX - r.left, e.clientY - r.top);
    };
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, [zoomBy]);

  // --- what is drawn ---------------------------------------------------------------------------------------------
  const points = useMemo(() => (zone ? poi.inZone(zone.map_id, types, side, layer) : []), [zone, types, side, layer]);
  // While a zoom glides, the icons keep their size and their merging of the zoom it started from and only move with
  // the map; they merge or split once, when it settles (recounting every frame made them jump).
  const [settled, setSettled] = useState<number | null>(null);
  useEffect(() => { if (view && !frame.current && view.zoom !== settled) setSettled(view.zoom); }, [view]); // eslint-disable-line react-hooks/exhaustive-deps
  const iconZoom = settled ?? view?.zoom ?? 1;
  const merged = useMemo(() => {
    if (iconZoom >= SPLIT_ZOOM) return points.map((p) => [p]);
    const base: View = { zoom: iconZoom, left: 0, top: 0 }; // the cells do not depend on panning (core cluster)
    return cluster(points, (x, y) => toScreen(base, x, y), iconSize("", iconZoom) * 1.1).map(([, , m]) => m);
  }, [points, iconZoom]);
  const groups = useMemo(() => {
    if (!view || !size) return [];
    const out: [number, number, Poi[]][] = merged.map((m) => {
      let x = 0, y = 0;
      for (const p of m) { const [sx, sy] = toScreen(view, p.x, p.y); x += sx; y += sy; }
      return [x / m.length, y / m.length, m];
    });
    // big landmarks at the bottom, teleporters and kisks on top
    const rank = (p: Poi) => (BIG_TYPES.has(p.type) ? 2 : p.type in ICON_SCALE ? 0 : 1);
    return out.filter(([x, y, m]) => {
      const s = iconSize(m[0].type, iconZoom);
      return x > -s && x < size.w + s && y > -s && y < size.h + s;
    }).sort((a, b) => rank(a[2][0]) - rank(b[2][0]));
  }, [merged, view, size, iconZoom]);
  const labels = useMemo(() => {
    if (!zone || !view || !size) return [];
    const levels = labelLevels(zone, iconZoom);
    if (!levels.size) return [];
    return zone.labels.map((label, i) => ({ label, i })).filter(({ label: [x, y, , level], i }) => {
      const onLayer = zone.label_layers[i];
      if (!levels.has(level) || (onLayer != null && layer !== null && onLayer !== layer)) return false;
      const [sx, sy] = toScreen(view, x, y);
      return sx > -200 && sx < size.w + 200 && sy > -60 && sy < size.h + 60;
    });
  }, [zone, view, size, layer, iconZoom]);
  const labelPx = Math.max(11, Math.min(20, Math.round((5 + 4 * iconZoom) * 1.33))); // settles with the zoom too
  const [bubble, setBubble] = useState<{ x: number; y: number; text: string } | null>(null);

  // --- the right panel -------------------------------------------------------------------------------------------
  const placeHere = shownPlace && zone && shownPlace.map_id === zone.map_id ? shownPlace : null;
  const pick = (p: Poi, centre = false) => {
    setSelected({ kind: "poi", poi: p });
    if (centre) flyTo(p.x, p.y, Math.max(viewRef.current?.zoom ?? 1, 1));
  };
  const near: Near[] = useMemo(() => {
    if (selected?.kind === "poi") return nearby(poi, selected.poi.zone, selected.poi.gx, selected.poi.gy, side, layer, selected.poi);
    if (placeHere) return nearby(poi, placeHere.map_id, placeHere.x, placeHere.y, side, layer);
    return [];
  }, [selected, placeHere, side, layer]);
  const clearPlace = () => { setShownPlace(null); onPlaceCleared(); };
  /** «Показать рядом»: the place and its nearest useful points fill the view. */
  const showNear = () => {
    if (!placeHere || !zone || !size) return;
    const [px, py] = toImage(zone, placeHere.x, placeHere.y);
    const spots = [[px, py], ...near.filter((n) => n.metres < 1500).map((n) => [n.poi.x, n.poi.y])];
    const xs = spots.map(([x]) => x), ys = spots.map(([, y]) => y);
    const w = Math.max(...xs) - Math.min(...xs) + 160, h = Math.max(...ys) - Math.min(...ys) + 160;
    const zoom = Math.min(size.w / w, size.h / h, MAX_ZOOM / ZOOM_STEP);
    flyTo((Math.max(...xs) + Math.min(...xs)) / 2, (Math.max(...ys) + Math.min(...ys)) / 2, zoom);
  };

  // --- search ----------------------------------------------------------------------------------------------------
  const search = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [at, setAt] = useState(-1);
  const matches: Match[] = useMemo(() => {
    if (!zone || !query.trim()) return [];
    const words = normalize(query).split(/\s+/).filter(Boolean);
    // a point's name, its type («Привратник») and its group («Телепорты»): «телепорт» finds the teleporters too
    const groupOf = (type: string) => Object.values(FILTER_GROUPS).find(([, kinds]) => kinds.includes(type))?.[0] ?? "";
    const found: Match[] = poi.inZone(zone.map_id, types, side, layer)
      .filter((p) => { const text = normalize(`${p.name} ${poi.typeName(p.type)} ${groupOf(p.type)}`); return words.every((w) => text.includes(w)); })
      .map((p) => ({ kind: "poi" as const, poi: p }));
    zone.labels.forEach(([x, y, text], i) => {
      const onLayer = zone.label_layers[i];
      if ((onLayer == null || layer === null || onLayer === layer) && words.every((w) => normalize(text).includes(w))) {
        found.push({ kind: "area", x, y, text: text.replace(/\n/g, " ") });
      }
    });
    return found;
  }, [zone, query, types, side, layer]);
  useEffect(() => setAt(-1), [matches]);
  const go = (step: number) => {
    if (!matches.length) return;
    const next = (at + step + matches.length) % matches.length;
    setAt(next);
    const m = matches[next];
    const zoom = Math.max(viewRef.current?.zoom ?? 1, 1);
    if (m.kind === "poi") pick(m.poi, true);
    else { setSelected({ kind: "area", x: m.x, y: m.y, text: m.text }); flyTo(m.x, m.y, zoom); }
  };
  useEffect(() => { // Ctrl+K: to the search field
    const keys = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); search.current?.focus(); search.current?.select(); }
    };
    window.addEventListener("keydown", keys);
    return () => window.removeEventListener("keydown", keys);
  }, []);

  // --- side, filters and zone ------------------------------------------------------------------------------------
  const [filters, setFilters] = useState(false);
  const filterBox = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!filters) return;
    const outside = (e: PointerEvent) => { if (!filterBox.current?.contains(e.target as Node)) setFilters(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setFilters(false); };
    window.addEventListener("pointerdown", outside);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("pointerdown", outside); window.removeEventListener("keydown", esc); };
  }, [filters]);
  const chooseSide = (value: string) => {
    setSide(value);
    boot.save({ map_side: value });
    if (zone && zone.side && zone.side !== value) { // this zone belongs to the other side: the first zone of this one
      const first = zonesOfSide(zones, value).find((z) => z.map_id === DEFAULT_ZONE) ?? zonesOfSide(zones, value)[0];
      if (first) openZone(first.map_id);
    }
  };
  const toggleGroup = (group: string) => {
    const next = hidden.includes(group) ? hidden.filter((g) => g !== group) : [...hidden, group];
    setHidden(next);
    boot.save({ map_hidden: next.filter((g) => g !== "quests"), map_quests: !next.includes("quests") });
    if (selected?.kind === "poi" && FILTER_GROUPS[group][1].includes(selected.poi.type) && !hidden.includes(group)) setSelected(null);
  };
  const openZone = (id: string) => {
    setZoneId(id);
    setLayer(zones[id]?.layers[0]?.[0] ?? null);
    setSelected(null);
    setQuery("");
  };
  const zoneList = useMemo(() => zonesOfSide(zones, side), [side]);

  const centreButton = () => {
    if (!zone || !size) return;
    if (placeHere) { const [ix, iy] = toImage(zone, placeHere.x, placeHere.y); flyTo(ix, iy); return; }
    const from = viewRef.current;
    const to = fitView(zone, size.w, size.h);
    if (from) animate((t) => ({ zoom: from.zoom * (to.zoom / from.zoom) ** t, left: from.left + (to.left - from.left) * t, top: from.top + (to.top - from.top) * t }), FLY_MS);
  };

  const backToPlace = () => { setSelected(null); centreButton(); };

  if (!zone) return <main className="soon"><p>Карт нет: папка data/maps не найдена.</p></main>;
  const [placeX, placeY] = placeHere ? toImage(zone, placeHere.x, placeHere.y) : [0, 0];
  const pin = placeHere && view ? toScreen(view, placeX, placeY) : null;

  return (
    <main className="map-page">
      <div className="map-bar">
        <label className="map-zone">
          <select className="field" value={zone.map_id} aria-label="Зона" onChange={(e) => openZone(e.target.value)}>
            {!zoneList.some((z) => z.map_id === zone.map_id) && <option value={zone.map_id}>{zone.name}</option>}
            {zoneList.map((z) => <option key={z.map_id} value={z.map_id}>{z.name}</option>)}
          </select>
        </label>
        {zone.layers.length > 0 && (
          <select className="field map-layer" value={layer ?? ""} aria-label="Слой Бездны" onChange={(e) => setLayer(Number(e.target.value))}>
            {zone.layers.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        )}
        <div className="map-search">
          <IconSearch />
          <input ref={search} className="field" placeholder="Поиск по карте (места, NPC, задания…)" value={query} aria-label="Поиск по карте"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); go(e.shiftKey ? -1 : 1); }
              if (e.key === "Escape") setQuery("");
            }} />
          {query.trim() ? <span className="map-found" aria-live="polite">{matches.length ? `${at >= 0 ? at + 1 : "–"} / ${matches.length}` : "нет"}</span>
            : <kbd>Ctrl + K</kbd>}
        </div>
        <div className="map-filters" ref={filterBox}>
          <button className={`btn${filters ? " on" : ""}`} aria-haspopup="dialog" aria-expanded={filters} onClick={() => setFilters(!filters)}>
            <IconFilter /> Фильтры{hidden.length > 0 && <span className="map-dot" aria-label="часть меток скрыта" />}
          </button>
          {filters && (
            <div className="map-pop" role="dialog" aria-label="Фильтры карты">
              <div className="lbl">Сторона</div>
              <div className="segmented" role="radiogroup" aria-label="Сторона">
                {Object.entries(SIDES).map(([value, title]) => (
                  <button key={value} role="radio" aria-checked={side === value} className={side === value ? "on" : ""} onClick={() => chooseSide(value)}>
                    {side === value && <Glide group="map-side" />}<span>{title}</span>
                  </button>
                ))}
              </div>
              <div className="lbl">Метки на карте</div>
              {Object.entries(FILTER_GROUPS).map(([group, [title, kinds]]) => (
                <label key={group} className="check map-check">
                  <input type="checkbox" checked={!hidden.includes(group)} onChange={() => toggleGroup(group)} />
                  <span className="box" />
                  {typeIcon(FILTER_ICON[group] ?? kinds[0]) && <img src={typeIcon(FILTER_ICON[group] ?? kinds[0])!} alt="" />}
                  <span>{title}</span>
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="map-body">
        <div ref={box} className={`map-view${dragging ? " dragging" : ""}`} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
          onPointerUp={onPointerUp} onPointerCancel={onPointerUp} onPointerLeave={() => setMouse(null)}
          onDoubleClick={(e) => { if (!(e.target as HTMLElement).closest("button")) { const [sx, sy] = local(e); zoomBy(2, sx, sy); } }}>
          {picture && view && (
            <img className="map-picture" src={picture} alt="" draggable={false}
              style={{ width: zone.size, height: zone.size, transform: `translate(${-view.left * view.zoom}px, ${-view.top * view.zoom}px) scale(${view.zoom})` }} />
          )}
          {pictureMissing && <div className="map-empty">Картинки этой зоны нет в data/maps.</div>}
          {view && labels.map(({ label: [x, y, text, level], i }) => {
            const [sx, sy] = toScreen(view, x, y);
            return <div key={i} className={`map-label ${level}`} style={{ left: sx, top: sy, fontSize: level === "zoom" ? labelPx - 2 : labelPx }}>{text}</div>;
          })}
          {view && groups.map(([sx, sy, members]) => {
            const first = members[0];
            const s = iconSize(first.type, iconZoom);
            const chosen = selected?.kind === "poi" && members.includes(selected.poi);
            const src = typeIcon(first.type);
            const title = members.length > 1
              ? Object.entries(members.reduce<Record<string, number>>((acc, m) => ({ ...acc, [m.type]: (acc[m.type] ?? 0) + 1 }), {}))
                .sort((a, b) => b[1] - a[1]).map(([t, n]) => `${poi.typeName(t)}: ${n}`).join("\n")
              : first.name ? `${first.name} · ${poi.typeName(first.type)}` : poi.typeName(first.type);
            return (
              <button key={members.map((m) => `${m.type}${m.x},${m.y}`).join("|")} className={`map-poi${chosen ? " chosen" : ""}`}
                style={{ left: sx, top: sy, width: s, height: s }} aria-label={title}
                onPointerEnter={() => setBubble({ x: sx, y: sy - s / 2, text: title })} onPointerLeave={() => setBubble(null)}
                onClick={() => {
                  if (drag.current?.moved) return;
                  if (members.length === 1) pick(first);
                  else zoomBy(2, sx, sy);
                }}>
                {src ? <img src={src} alt="" draggable={false} /> : <i />}
                {members.length > 1 && <b className="map-count">{members.length < 100 ? members.length : "99+"}</b>}
              </button>
            );
          })}
          {pin && placeHere && (
            <div className="map-pin" style={{ left: pin[0], top: pin[1] }}>
              <span className="glow" />
              {PLACE_ICON ? <img src={PLACE_ICON} alt="" width={PLACE_ICON_PX} height={PLACE_ICON_PX} draggable={false} /> : <span className="cross">+</span>}
              <b>{placeHere.label}</b>
            </div>
          )}
          {bubble && !dragging && <div className="map-bubble" style={{ left: bubble.x, top: bubble.y }}>{bubble.text}</div>}
          {placeHere && <div className="map-badge"><i />Выбрана метка из чата</div>}
          {mouse && <div className="map-coords">x {Math.round(mouse[0])} · y {Math.round(mouse[1])}</div>}
          <div className="map-zoom">
            <button aria-label="Приблизить (или колесо мыши)" title="Приблизить" onClick={() => size && zoomBy(ZOOM_STEP, size.w / 2, size.h / 2)}><IconPlus /></button>
            <button aria-label="Отдалить (или колесо мыши)" title="Отдалить" onClick={() => size && zoomBy(1 / ZOOM_STEP, size.w / 2, size.h / 2)}><IconMinus /></button>
          </div>
          <button className="map-locate" aria-label={placeHere ? "К метке из чата" : "Вся карта"} title={placeHere ? "К метке из чата" : "Вся карта"}
            onClick={centreButton}>{placeHere ? <IconTarget /> : <IconFit />}</button>
        </div>

        <aside className="map-panel" aria-label="Выбранное на карте">
          {selected?.kind === "poi" ? (
            <PointCard title={selected.poi.name || poi.typeName(selected.poi.type)} kind={poi.typeName(selected.poi.type)} icon={typeIcon(selected.poi.type)}
              coords={[selected.poi.gx, selected.poi.gy]} note={selected.poi.note} near={near} onNear={(p) => pick(p, true)}
              onClose={() => setSelected(null)} onBack={placeHere ? backToPlace : null} />
          ) : selected?.kind === "area" ? (
            <PointCard title={selected.text} kind="Район" icon={null} coords={null} note="" near={[]} onNear={() => {}}
              onClose={() => setSelected(null)} onBack={placeHere ? backToPlace : null} />
          ) : placeHere ? (
            <div className="map-card">
              <div className="map-card-head">
                <h2>Место из чата</h2>
                <button className="x" aria-label="Убрать метку" onClick={clearPlace}><IconClose /></button>
              </div>
              <div className="map-msg-meta"><IconMessage /><span>Сообщение</span>{placeHere.time && <><i>·</i><span>{placeHere.time.slice(0, 5)}</span></>}</div>
              {placeHere.text && <p className="map-msg">{placeHere.nick && <b>{placeHere.nick}: </b>}{placeHere.text}</p>}
              <div className="map-opened">Открыто по ссылке «{placeHere.label}»</div>
              <div className="map-preview" aria-hidden="true">
                {picture && <img className="pic" src={picture} alt="" draggable={false}
                  style={{ width: zone.size, height: zone.size, left: `calc(50% - ${placeX}px)`, top: `calc(50% - ${placeY}px)` }} />}
                {PLACE_ICON && <img className="mark" src={PLACE_ICON} alt="" />}
                <span>{zone.name}</span>
              </div>
              <button className="btn primary map-near-btn" onClick={showNear}><IconNavigate /> Показать рядом</button>
              <button className="btn map-clear" onClick={clearPlace}>Убрать метку</button>
              <NearList near={near} onNear={(p) => pick(p, true)} />
            </div>
          ) : (
            <div className="map-card map-hint">
              <h2>{zone.name}</h2>
              <p>Кликни по значку на карте или найди точку поиском — здесь появится карточка и что рядом.</p>
              <p>Ссылка «Место» в чате открывает карту на этом месте.</p>
            </div>
          )}
        </aside>
      </div>
    </main>
  );
}

/** A picked point (or an area of the search): what it is, where, and the nearest useful points. */
function PointCard({ title, kind, icon, coords, note, near, onNear, onClose, onBack }: {
  title: string; kind: string; icon: string | null; coords: [number, number] | null; note: string; near: Near[];
  onNear(p: Poi): void; onClose(): void; onBack: (() => void) | null;
}) {
  return (
    <div className="map-card">
      <div className="map-card-head">
        <div className="map-point-title">
          {icon && <img src={icon} alt="" />}
          <div><span className="muted">{kind}</span><h2>{title}</h2></div>
        </div>
        <button className="x" aria-label="Закрыть" onClick={onClose}><IconClose /></button>
      </div>
      {coords && <div className="muted map-xy">x {Math.round(coords[0])} · y {Math.round(coords[1])}</div>}
      {note && <p className="map-note">{note}</p>}
      {onBack && <button className="btn map-clear" onClick={onBack}>К метке из чата</button>}
      <NearList near={near} onNear={onNear} />
    </div>
  );
}

/** «Рядом»: the nearest teleporter, kisk, warehouse, merchant, stigma master and artifact, with the distance. */
function NearList({ near, onNear }: { near: Near[]; onNear(p: Poi): void }) {
  if (!near.length) return null;
  return (
    <>
      <h3 className="map-near-title">Рядом</h3>
      <ul className="map-near">
        {near.map((n) => (
          <Fragment key={n.type}>
            <li>
              <button onClick={() => onNear(n.poi)}>
                {typeIcon(n.type) ? <img src={typeIcon(n.type)!} alt="" /> : <i />}
                <span className="t"><b>{n.poi.name || n.typeName}</b><span>{n.typeName}</span></span>
                <span className="m">{metresText(n.metres)}</span>
                <IconChevron open={false} />
              </button>
            </li>
          </Fragment>
        ))}
      </ul>
    </>
  );
}
