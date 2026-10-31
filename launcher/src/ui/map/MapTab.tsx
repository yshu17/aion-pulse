// The «Карта» tab: a zone of Aion with its area names and points (teleporters, kisks, merchants, fortresses …) drawn
// with the game's own map icons, as Pulse's map (watcher/mapview.py). The wheel zooms to the mouse, dragging moves the
// map. A click on an icon picks it (a group of icons: zooms in on it). A place link from the chat opens here as a blue cross; the right panel shows it (or
// the picked point) and what is near it. The rules of the view live in core/map/view.ts.
import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { normalize } from "../../core/chat/matcher";
import { cluster, Poi } from "../../core/map/poi";
import {
  centreOn, clampView, fitView, fitZoom, gameAt, iconSize, labelLevels, MAX_ZOOM, nearby, Near, shownTypes, toScreen,
  toGame, View, ZOOM_STEP, zonesOfSide, zoomAt, BIG_TYPES, ICON_SCALE,
} from "../../core/map/view";
import { FILTER_GROUPS, SIDES, toImage, Zone } from "../../core/map/zones";
import { nearestPoint, spawnAreas, SpawnPoint, Spawns } from "../../core/map/spawns";
import { metresText, plural } from "../../core/text";
import { Glide } from "../fx";
import { IconChevron, IconClose, IconFilter, IconLeft, IconFit, IconMessage, IconMinus, IconNavigate, IconPlus, IconReset, IconSearch, IconTarget } from "../icons";
import type { Boot } from "../useBoot";
import { posLink } from "../../core/map/gathering";
import { copyText, GatherPanel } from "./GatherPanel";
import { gatherIcon, gathering, loadSpawns, pictureUrl, PLACE_ICON, poi, typeIcon, Way, wayFrom, waysInto, zones } from "./mapData";
import type { ChatPlace, MapTarget } from "./placeLink";
import { regionOf, world, WorldLayer, zoneTitle } from "./WorldLayer";
import "./map.css";

const DEFAULT_ZONE = "220070000"; // Келькмарос
const SPLIT_ZOOM = (MAX_ZOOM / ZOOM_STEP) * 0.999; // the last two zoom levels: every point its own icon, no counts
const PLACE_ICON_PX = 17; // the blue cross of the chat's place (and your mark), half the game's size
const FLY_MS = 260;
const FILTER_ICON: Record<string, string> = { rifts: "tunnel" }; // the group's icon in «Фильтры»: the Silentera tunnel for the rifts
const ZOOM_MS = 170;

type Selected = { kind: "poi"; poi: Poi } | { kind: "area"; x: number; y: number; text: string } | null;
type Match = { kind: "poi"; poi: Poi } | { kind: "area"; x: number; y: number; text: string };
/** The blue spawn area drawn around each point of a found NPC, in game metres (the client gives no spawn radius). */
const SPAWN_RADIUS_M = 110;
const MARKS_KEY = "pulse.map.marks";
const MARK_NAME = "Метка";

/** An area name: the data writes some twice on two lines («Око Арэшурата|Око Арэшурата»), shown once. */
const oneLine = (text: string) => text.split("\n").filter((line, i, all) => all.indexOf(line) === i).join("\n");

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
const ease = (t: number) => 1 - (1 - t) ** 3;

export function MapTab({ boot, target, home, onPlaceCleared }: {
  boot: Boot; target: (MapTarget & { n: number }) | null; home: number; onPlaceCleared(): void;
}) {
  const place = target?.type === "place" ? target : null;
  const cfg = boot.config;
  const [side, setSide] = useState(cfg.map_side in SIDES ? cfg.map_side : "dark");
  const [hidden, setHidden] = useState<string[]>(() => [...cfg.map_hidden.filter((g) => g in FILTER_GROUPS), ...(cfg.map_quests ? [] : ["quests"])]);
  const types = useMemo(() => shownTypes(poi, hidden), [hidden]);
  const [zoneId, setZoneId] = useState(() => target?.map_id ?? (DEFAULT_ZONE in zones ? DEFAULT_ZONE : Object.keys(zones)[0]));
  const zone: Zone | undefined = zones[zoneId];
  const [layer, setLayer] = useState<number | null>(zone?.layers[0]?.[0] ?? null);
  const [selected, setSelected] = useState<Selected>(null);
  const [shownPlace, setShownPlace] = useState<ChatPlace | null>(place);
  // the tab opens on Atreia (the world map), a region of it, or a zone; a place from the chat opens its zone at once
  const [level, setLevel] = useState<"world" | "zone">(target ? "zone" : "world");
  const [region, setRegion] = useState<string | null>(null);
  const goHome = () => { setLevel("world"); setRegion(null); };
  useEffect(() => { if (home) goHome(); }, [home]);
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

  // the zone of a place or an NPC to show: its side, its first layer; the map flies there once it is drawn
  const pendingPlace = useRef<{ map_id: string; x: number; y: number } | null>(null);
  const goToZone = (mapId: string) => {
    const z = zones[mapId];
    if (!z) return false;
    setLevel("zone");
    if (z.side && z.side !== side) setSide(z.side);
    if (mapId !== zoneId) {
      setZoneId(mapId);
      setLayer(z.layers[0]?.[0] ?? null);
    }
    return true;
  };

  // NPCs and monsters (data/maps/spawns.json, read on the first search): one NPC's points in one zone at a time
  const [spawns, setSpawns] = useState<Spawns | null>(null);
  const needSpawns = () => { if (!spawns) loadSpawns().then(setSpawns); };
  const [npcFocus, setNpcFocus] = useState<{ npc: string; name: string; map_id: string; points: SpawnPoint[]; at: number } | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const showNpc = async (npc: string, name: string, mapId: string, at?: [number, number]) => {
    const index = spawns ?? await loadSpawns();
    setSpawns(index);
    const points = index.points(npc, mapId);
    if (!points.length || !goToZone(mapId)) return;
    const near = at ? nearestPoint(points, at[0], at[1]) : null;
    const i = near ? points.indexOf(near) : 0;
    setSelected(null);
    setSearchOpen(false);
    setNpcFocus({ npc, name, map_id: mapId, points, at: i });
    pendingPlace.current = { map_id: mapId, x: points[i][0], y: points[i][1] };
  };

  useEffect(() => {
    if (!target) return;
    if (target.type === "npc") { showNpc(target.npc, target.name, target.map_id, target.at); return; }
    setShownPlace(target);
    setSelected(null);
    setNpcFocus(null);
    if (goToZone(target.map_id)) pendingPlace.current = target;
  }, [target?.n]); // eslint-disable-line react-hooks/exhaustive-deps
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
    if (e.button !== 0 || !view || level !== "zone") return;
    stop();
    // the pointer is captured only once the mouse really drags: a plain click must still reach the icon under it
    drag.current = { x: e.clientX, y: e.clientY, view, moved: false };
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (zone && view) setMouse(gameAt(view, zone, ...local(e)));
    const d = drag.current;
    if (!d || !zone || !size) return;
    const dx = e.clientX - d.x, dy = e.clientY - d.y;
    if (!d.moved && Math.abs(dx) < 4 && Math.abs(dy) < 4) return;
    if (!d.moved) { d.moved = true; setDragging(true); setBubble(null); (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId); }
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
    if (level !== "zone") return;
    el.addEventListener("wheel", wheel, { passive: false });
    return () => el.removeEventListener("wheel", wheel);
  }, [zoomBy, level]);

  // your own marks (Ctrl + right button): one per zone and layer, kept between runs, copied as the game's place link
  const [marks, setMarks] = useState<Record<string, [number, number]>>(() => {
    try { return JSON.parse(localStorage.getItem(MARKS_KEY) ?? "{}"); } catch { return {}; }
  });
  const markKey = zone ? `${zone.map_id}:${layer ?? ""}` : "";
  const saveMarks = (next: Record<string, [number, number]>) => {
    setMarks(next);
    try { localStorage.setItem(MARKS_KEY, JSON.stringify(next)); } catch { /* private mode: the mark lives until the window closes */ }
  };
  const onContextMenu = (e: React.MouseEvent) => {
    if (!e.ctrlKey || !zone || !view || level !== "zone") return;
    e.preventDefault();
    const [sx, sy] = local(e);
    const g = gameAt(view, zone, sx, sy);
    if (!g) return;
    saveMarks({ ...marks, [markKey]: [Math.round(g[0] * 10) / 10, Math.round(g[1] * 10) / 10] });
    copyText(posLink(MARK_NAME, zone.map_id, [g[0], g[1]])).then((done) =>
      notify(done ? "Метка поставлена и скопирована в буфер" : "Метка поставлена"));
  };

  // --- what is drawn ---------------------------------------------------------------------------------------------
  const points = useMemo(() => (zone ? poi.inZone(zone.map_id, types, side, layer) : []), [zone, types, side, layer]);
  // While a zoom glides, the icons keep their size and their merging of the zoom it started from and only move with
  // the map; they merge or split once, when it settles (recounting every frame made them jump).
  const [settled, setSettled] = useState<number | null>(null);
  useEffect(() => { if (view && !frame.current && view.zoom !== settled) setSettled(view.zoom); }, [view]); // eslint-disable-line react-hooks/exhaustive-deps
  const iconZoom = settled ?? view?.zoom ?? 1;
  // a stable id per point: the data has points of one type at one spot twice (the Abyss: 62), keys must not collide
  const pointIds = useMemo(() => new Map(points.map((p, i) => [p, i])), [points]);
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
    // drawn last = on top: fortresses over everything, then teleporters and kisks, then the other landmarks (dungeon
    // entrances, the tunnel, artifacts: the big ones must stay clickable under nothing), the ordinary points at the bottom
    const rank = (p: Poi) => (p.type === "fortress" ? 3 : BIG_TYPES.has(p.type) ? 2 : p.type in ICON_SCALE ? 1 : 0);
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
  // gathering nodes switched on in «Сбор» (by node id: the same node stays on in the next zone), their spots on screen
  const gather = useMemo(() => gathering.inZone(zoneId, layer), [zoneId, layer]);
  const [gatherShown, setGatherShown] = useState<string[]>([]);
  // switching a resource on centres the map on its spot nearest to the middle of the view (no blinking: only a focus)
  const toggleGather = (id: string) => {
    if (gatherShown.includes(id)) {
      setGatherShown(gatherShown.filter((i) => i !== id));
      return;
    }
    setGatherShown([...gatherShown, id]);
    const node = [...gather.essence, ...gather.aether].find((n) => n.id === id);
    const from = viewRef.current;
    if (!node || !zone || !size || !from) return;
    // the spot nearest to the middle of the view (the first one when the map has not moved yet)
    const cx = from.left + size.w / 2 / from.zoom, cy = from.top + size.h / 2 / from.zoom;
    let best = 0, bestD = Infinity;
    node.points.forEach(([gx, gy], i) => {
      const [ix, iy] = toImage(zone, gx, gy);
      const d = Math.hypot(ix - cx, iy - cy);
      if (d < bestD) { best = i; bestD = d; }
    });
    const [ix, iy] = toImage(zone, node.points[best][0], node.points[best][1]);
    flyTo(ix, iy, Math.max(from.zoom, fitZoom(zone, size.w, size.h) * 2));
  };
  const gatherSpots = useMemo(() => {
    if (!zone || !gatherShown.length) return [];
    return [...gather.essence, ...gather.aether].filter((n) => gatherShown.includes(n.id))
      .flatMap((n) => n.points.map(([gx, gy], i) => ({ node: n, i, at: toImage(zone, gx, gy) })));
  }, [zone, gather, gatherShown]);
  const gatherPx = Math.round(Math.max(18, Math.min(28, 14 + 4 * iconZoom)) * 1.25);
  const [bubble, setBubble] = useState<{ x: number; y: number; text: string } | null>(null);
  // a short notice at the bottom of the map («Метка скопирована в буфер»)
  const [notice, setNotice] = useState<{ text: string; n: number } | null>(null);
  const noticeTimer = useRef(0);
  const notify = (text: string) => {
    setNotice((was) => ({ text, n: (was?.n ?? 0) + 1 }));
    clearTimeout(noticeTimer.current);
    noticeTimer.current = window.setTimeout(() => setNotice(null), 2200);
  };
  useEffect(() => () => clearTimeout(noticeTimer.current), []);

  // --- the right panel -------------------------------------------------------------------------------------------
  const placeHere = shownPlace && zone && shownPlace.map_id === zone.map_id ? shownPlace : null;
  const npcHere = npcFocus && zone && npcFocus.map_id === zone.map_id ? npcFocus : null;
  const pick = (p: Poi, centre = false) => {
    setSelected({ kind: "poi", poi: p });
    if (centre) flyTo(p.x, p.y, Math.max(viewRef.current?.zoom ?? 1, 1));
  };
  const near: Near[] = useMemo(() => {
    if (selected?.kind === "poi") return nearby(poi, selected.poi.zone, selected.poi.gx, selected.poi.gy, side, layer, selected.poi);
    if (selected?.kind === "area" && zone) {
      const g = toGame(zone, selected.x, selected.y);
      return g ? nearby(poi, zone.map_id, g[0], g[1], side, layer) : [];
    }
    if (npcHere) { const [gx, gy] = npcHere.points[npcHere.at]; return nearby(poi, npcHere.map_id, gx, gy, side, layer); }
    if (placeHere) return nearby(poi, placeHere.map_id, placeHere.x, placeHere.y, side, layer);
    return [];
  }, [selected, zone, placeHere, npcHere, side, layer]);
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
  const searchBox = useRef<HTMLDivElement>(null);
  const npcHits = useMemo(() => (spawns && query.trim().length >= 2 ? spawns.find(query, 8) : []), [spawns, query]);
  useEffect(() => {
    if (!searchOpen) return;
    const outside = (e: PointerEvent) => { if (!searchBox.current?.contains(e.target as Node)) setSearchOpen(false); };
    window.addEventListener("pointerdown", outside);
    return () => window.removeEventListener("pointerdown", outside);
  }, [searchOpen]);
  const focusNpcPoint = (i: number) => {
    if (!npcFocus || !zone) return;
    setSelected(null);
    setNpcFocus({ ...npcFocus, at: i });
    const [ix, iy] = toImage(zone, npcFocus.points[i][0], npcFocus.points[i][1]);
    flyTo(ix, iy, Math.max(viewRef.current?.zoom ?? 1, 1));
  };
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
        found.push({ kind: "area", x, y, text: oneLine(text).replace(/\n/g, " ") });
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
    setLevel("zone");
    setNpcFocus(null);
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

  /** «Сбросить»: no picked point, NPC or chat place, and the whole zone in view as it opened. */
  const resetMap = () => {
    setSelected(null);
    setNpcFocus(null);
    setBubble(null);
    setGatherShown([]);
    if (Object.keys(marks).length) saveMarks({});
    if (shownPlace) clearPlace();
    if (zone && size) {
      const from = viewRef.current, to = fitView(zone, size.w, size.h);
      if (from) animate((t) => ({ zoom: from.zoom * (to.zoom / from.zoom) ** t, left: from.left + (to.left - from.left) * t, top: from.top + (to.top - from.top) * t }), FLY_MS);
    }
  };
  const backToPlace = () => { setSelected(null); centreButton(); };
  /** A way to another zone (a teleport statue of a capital, its temple's way back): that zone, at the point it arrives. */
  /** Back out of a dungeon: the zone of its entrance, the entrance picked. */
  const goOut = (way: Way) => {
    openZone(way.from);
    const z = zones[way.from];
    if (z?.side && z.side !== side) setSide(z.side);
    const entrance = poi.zone(way.from).find((p) => p.type === "dungeon" && p.name === way.name);
    if (entrance) {
      setSelected({ kind: "poi", poi: entrance });
      pendingPlace.current = { map_id: way.from, x: entrance.gx, y: entrance.gy };
    }
  };
  const goWay = (way: Way) => {
    const target = zones[way.to];
    if (!target) return;
    openZone(way.to);
    if (target.side && target.side !== side) setSide(target.side);
    const arrive = way.at
      ? poi.zone(way.to).filter((p) => p.type === "teleport" || p.type === "portal")
        .sort((a, b) => Math.hypot(a.gx - way.at![0], a.gy - way.at![1]) - Math.hypot(b.gx - way.at![0], b.gy - way.at![1]))[0]
      : undefined;
    if (arrive) {
      setSelected({ kind: "poi", poi: arrive });
      pendingPlace.current = { map_id: way.to, x: arrive.gx, y: arrive.gy };
    }
  };
  // the breadcrumb: Атрея / the region / the zone (a zone outside the world map, e.g. a temple: Атрея / the zone)
  const crumbRegion = level === "world" ? region : regionOf(zoneId);
  const worldZone = Object.values(world.regions).flatMap((r) => r.zones).find((z) => z.map_id === zoneId && (z.layer === null || z.layer === layer));
  const crumbZone = worldZone ? zoneTitle(worldZone) : zone?.name ?? "";

  if (!zone) return <main className="soon"><p>Карт нет: папка data/maps не найдена.</p></main>;
  const [placeX, placeY] = placeHere ? toImage(zone, placeHere.x, placeHere.y) : [0, 0];
  const pin = placeHere && view ? toScreen(view, placeX, placeY) : null;

  return (
    <main className="map-page">
      <div className="map-bar">
        {(level === "zone" || region) && (
          <button className="btn map-home" title="К карте мира" onClick={() => (level === "zone" && regionOf(zoneId) ? (setLevel("world"), setRegion(regionOf(zoneId))) : goHome())}>
            <IconLeft /> {level === "zone" && regionOf(zoneId) ? world.regions[regionOf(zoneId)!].title : "Атрея"}
          </button>
        )}
        <label className="map-zone">
          <select className="field" value={zone.map_id} aria-label="Зона" onChange={(e) => openZone(e.target.value)}>
            {!zoneList.some((z) => z.map_id === zone.map_id) && <option value={zone.map_id}>{zone.name}</option>}
            <optgroup label="Локации">
              {zoneList.filter((z) => z.kind === "zone").map((z) => <option key={z.map_id} value={z.map_id}>{z.name}</option>)}
            </optgroup>
            <optgroup label="Данжи">
              {zoneList.filter((z) => z.kind === "instance").map((z) => <option key={z.map_id} value={z.map_id}>{z.name}</option>)}
            </optgroup>
          </select>
        </label>
        {level === "zone" && zone.layers.length > 0 && (
          <select className="field map-layer" value={layer ?? ""} aria-label="Слой Бездны" onChange={(e) => setLayer(Number(e.target.value))}>
            {zone.layers.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
        )}
        {level === "zone" ? <>
        <div className="map-search" ref={searchBox}>
          <IconSearch />
          <input ref={search} className="field" placeholder="Поиск по карте (места, NPC, монстры…)" value={query} aria-label="Поиск по карте"
            aria-expanded={searchOpen && query.trim().length >= 2} aria-controls="map-results"
            onFocus={() => { needSpawns(); setSearchOpen(true); }}
            onChange={(e) => { setQuery(e.target.value); needSpawns(); setSearchOpen(true); }}
            onKeyDown={(e) => {
              if (e.key === "Enter") { e.preventDefault(); go(e.shiftKey ? -1 : 1); }
              if (e.key === "Escape") { if (searchOpen) setSearchOpen(false); else setQuery(""); }
            }} />
          {searchOpen && query.trim().length >= 2 && (
            <div className="map-results" id="map-results" aria-label="Найдено">
              <div className="map-results-head">
                <span>На этой карте: {matches.length || "нет"}</span>
                {matches.length > 0 && <span className="muted">Enter — следующее, Shift+Enter — назад</span>}
              </div>
              <div className="map-results-head"><span>НПС и монстры во всех зонах</span>{!spawns && <span className="muted">загружаю…</span>}</div>
              {spawns && !npcHits.length && <div className="map-results-empty">Никого с таким именем</div>}
              {npcHits.map((hit) => {
                const first = hit.zones.find((z) => z.map_id === zoneId) ?? hit.zones[0];
                const others = hit.zones.filter((z) => z !== first);
                return (
                  <div key={hit.npc} className="map-result">
                    <button className="map-result-main" onClick={() => showNpc(hit.npc, hit.name, first.map_id)}>
                      <b>{hit.name}</b>
                      <span className="muted">{zones[first.map_id]?.name ?? first.map_id} · {plural(first.count, "точка", "точки", "точек")}</span>
                    </button>
                    {others.length > 0 && (
                      <div className="map-result-zones">
                        {others.slice(0, 3).map((z) => (
                          <button key={z.map_id} onClick={() => showNpc(hit.npc, hit.name, z.map_id)}>{zones[z.map_id]?.name ?? z.map_id} · {z.count}</button>
                        ))}
                        {others.length > 3 && <span className="muted">ещё {others.length - 3}</span>}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {query.trim() ? <span className="map-found" aria-live="polite">{matches.length ? `${at >= 0 ? at + 1 : "–"} / ${matches.length}` : "нет"}</span>
            : <kbd>Ctrl + K</kbd>}
        </div>
        <button className="btn" onClick={resetMap} title="Убрать выбор, метки и сбор с карты, вернуть карту в исходное положение"><IconReset /> Сбросить</button>
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
        </> : <div className="map-bar-hint">Выбери часть Атреи, потом зону, или найди зону в списке слева.</div>}
      </div>

      <div className="map-body">
        <div ref={box} className={`map-view${dragging ? " dragging" : ""}`} onPointerDown={onPointerDown} onPointerMove={onPointerMove}
          onPointerUp={onPointerUp} onPointerCancel={onPointerUp} onPointerLeave={() => setMouse(null)} onContextMenu={onContextMenu}>
          <nav className="map-crumbs" aria-label="Где на карте">
            <button className={level === "world" && !region ? "on" : ""} onClick={() => { setLevel("world"); setRegion(null); }}>Атрея</button>
            {crumbRegion && <><i>/</i><button className={level === "world" ? "on" : ""} onClick={() => { setLevel("world"); setRegion(crumbRegion); }}>{world.regions[crumbRegion].title}</button></>}
            {level === "zone" && <><i>/</i><span className="on">{crumbZone}</span></>}
          </nav>
          {level === "world" ? (size && <WorldLayer size={size} region={region} onRegion={setRegion}
            onZone={(z) => { if (!z.map_id) return; openZone(z.map_id); if (z.layer !== null) setLayer(z.layer); }} />) : <>
          {picture && view && (
            <img className="map-picture" src={picture} alt="" draggable={false}
              style={{ width: zone.size, height: zone.size, transform: `translate(${-view.left * view.zoom}px, ${-view.top * view.zoom}px) scale(${view.zoom})` }} />
          )}
          {pictureMissing && <div className="map-empty">Картинки этой зоны нет в data/maps.</div>}
          {view && labels.map(({ label: [x, y, text, level], i }) => {
            const [sx, sy] = toScreen(view, x, y);
            return <div key={i} className={`map-label ${level}`} style={{ left: sx, top: sy, fontSize: level === "zoom" ? labelPx - 2 : labelPx }}>{oneLine(text)}</div>;
          })}
          {view && selected?.kind === "area" && (() => {
            const [sx, sy] = toScreen(view, selected.x, selected.y);
            return <div className="map-area-pin" style={{ left: sx, top: sy }} aria-hidden="true"><i /></div>;
          })()}
          {npcHere && view && size && spawnAreas(npcHere.points, SPAWN_RADIUS_M).map((area, i) => {
            // the NPC's spawn areas, as the game's map: one blue glow for points close together, its own for a far one
            const d = area.r * 2 * Math.abs(zone.kx[0] || 1) * view.zoom;
            const [sx, sy] = toScreen(view, ...toImage(zone, area.x, area.y));
            if (sx < -d || sy < -d || sx > size.w + d || sy > size.h + d) return null;
            return <div key={`spawn${i}`} className="map-spawn" style={{ left: sx, top: sy, width: d, height: d }} />;
          })}
          {view && marks[markKey] && (() => {
            const [sx, sy] = toScreen(view, ...toImage(zone, marks[markKey][0], marks[markKey][1]));
            return (
              <button key={marks[markKey].join()} className="map-mark" style={{ left: sx, top: sy }} aria-label="Моя метка: скопировать ссылку"
                onPointerEnter={() => setBubble({ x: sx, y: sy - 18, text: "Моя метка\nклик — копировать, Ctrl + ПКМ — переставить" })} onPointerLeave={() => setBubble(null)}
                onClick={() => { if (!drag.current?.moved) copyText(posLink(MARK_NAME, zone.map_id, marks[markKey])).then((ok) => ok && notify("Метка скопирована в буфер")); }}>
                {PLACE_ICON ? <img src={PLACE_ICON} alt="" draggable={false} /> : <i />}
              </button>
            );
          })()}
          {view && size && gatherSpots.map(({ node, i, at: [ix, iy] }) => {
            const [sx, sy] = toScreen(view, ix, iy);
            if (sx < -gatherPx || sy < -gatherPx || sx > size.w + gatherPx || sy > size.h + gatherPx) return null;
            const src = gatherIcon(node.icon);
            const text = `${node.level} – ${node.name}\nклик — копировать ссылку на точку`;
            return (
              <button key={`${node.id}:${node.layer ?? ""}:${i}`} className="map-gather" style={{ left: sx, top: sy, width: gatherPx, height: gatherPx }}
                aria-label={`${node.level} – ${node.name}: копировать ссылку на точку`}
                onPointerEnter={() => setBubble({ x: sx, y: sy - gatherPx / 2, text })} onPointerLeave={() => setBubble(null)}
                onClick={() => {
                  if (drag.current?.moved) return;
                  copyText(posLink(node.name, zone.map_id, node.points[i])).then((done) => {
                    if (done) notify(`Метка «${node.name}» скопирована в буфер`);
                  });
                }}>
                {src ? <img src={src} alt="" draggable={false} /> : <i />}
              </button>
            );
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
              <button key={members.map((m) => pointIds.get(m)).join("|")} className={`map-poi${chosen ? " chosen" : ""}`}
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
          {npcHere && view && npcHere.points.map(([gx, gy], i) => {
            const [sx, sy] = toScreen(view, ...toImage(zone, gx, gy));
            if (sx < -20 || sy < -20 || sx > (size?.w ?? 0) + 20 || sy > (size?.h ?? 0) + 20) return null;
            return (
              <button key={i} className={`map-npc${i === npcHere.at ? " chosen" : ""}`} style={{ left: sx, top: sy }}
                aria-label={`${npcHere.name}, точка ${i + 1}`} onClick={() => { if (!drag.current?.moved) focusNpcPoint(i); }}
                onPointerEnter={() => setBubble({ x: sx, y: sy - 10, text: npcHere.name })} onPointerLeave={() => setBubble(null)} />
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
          {notice && <div key={notice.n} className="map-notice" role="status">{notice.text}</div>}
          {mouse && <div className="map-coords">x {Math.round(mouse[0])} · y {Math.round(mouse[1])}</div>}
          <div className="map-zoom">
            <button aria-label="Приблизить (или колесо мыши)" title="Приблизить" onClick={() => size && zoomBy(ZOOM_STEP, size.w / 2, size.h / 2)}><IconPlus /></button>
            <button aria-label="Отдалить (или колесо мыши)" title="Отдалить" onClick={() => size && zoomBy(1 / ZOOM_STEP, size.w / 2, size.h / 2)}><IconMinus /></button>
          </div>
          <button className="map-locate" aria-label={placeHere ? "К метке из чата" : "Вся карта"} title={placeHere ? "К метке из чата" : "Вся карта"}
            onClick={centreButton}>{placeHere ? <IconTarget /> : <IconFit />}</button>
          </>}
        </div>

        {level === "world" && (
          <aside className="map-panel" aria-label="Части Атреи">
            <div className="map-card map-hint">
              <h2>{region ? world.regions[region].title : "Атрея"}</h2>
              <p>{region ? "Выбери зону на карте или в списке." : "Выбери часть мира на глобусе или в списке."}</p>
              {shownPlace && zones[shownPlace.map_id] && (
                <button className="btn primary map-near-btn" onClick={() => { setLevel("zone"); if (zoneId !== shownPlace.map_id) openZone(shownPlace.map_id); pendingPlace.current = shownPlace; }}>
                  <IconTarget /> К метке из чата
                </button>
              )}
              <ul className="map-near">
                {region ? world.regions[region].zones.filter((z) => z.map_id && zones[z.map_id]).map((z) => (
                  <li key={z.code}><button onClick={() => { openZone(z.map_id!); if (z.layer !== null) setLayer(z.layer); }}>
                    <span className="t"><b>{zoneTitle(z)}</b><span>{z.layer !== null ? "Арэшурат" : world.regions[region].title}</span></span>
                    <IconChevron open={false} /></button></li>
                )) : Object.entries(world.regions).map(([key, r]) => (
                  <li key={key}><button onClick={() => setRegion(key)}>
                    <span className="t"><b>{r.title}</b><span>{r.zones.length} {r.zones.length === 3 ? "зоны" : "зон"}</span></span>
                    <IconChevron open={false} /></button></li>
                ))}
              </ul>
            </div>
          </aside>
        )}
        {level === "zone" && <aside className="map-panel" aria-label="Выбранное на карте">
          {selected?.kind === "poi" ? (
            <PointCard title={selected.poi.name || poi.typeName(selected.poi.type)} kind={poi.typeName(selected.poi.type)} icon={typeIcon(selected.poi.type)}
              coords={[selected.poi.gx, selected.poi.gy]} note={selected.poi.note} near={near} onNear={(p) => pick(p, true)}
              way={wayFrom(selected.poi.zone, selected.poi.name)} onWay={goWay}
              onClose={() => setSelected(null)} onBack={placeHere ? backToPlace : null} />
          ) : selected?.kind === "area" ? (
            <PointCard title={selected.text} kind="Район" icon={null} coords={null} note="" near={near} onNear={(p) => pick(p, true)}
              onClose={() => setSelected(null)} onBack={placeHere ? backToPlace : null} />
          ) : npcHere ? (
            <NpcCard npc={npcHere} zone={zone} near={near} onPoint={focusNpcPoint} onNear={(p) => pick(p, true)} onClose={() => setNpcFocus(null)} />
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
              {waysInto(zone.map_id).length > 0 && (
                <>
                  <h3 className="map-near-title">Выход</h3>
                  <ul className="map-near">
                    {waysInto(zone.map_id).map((w) => (
                      <li key={`${w.from}${w.name}`}><button onClick={() => goOut(w)}>
                        <span className="t"><b>{zones[w.from].name}</b><span>{w.name}</span></span><IconChevron open={false} />
                      </button></li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
          <GatherPanel nodes={gather} mapId={zone.map_id} onCopied={(name) => notify(`Метка «${name}» скопирована в буфер`)} shown={gatherShown} onToggle={toggleGather} onClear={() => setGatherShown([])} />
        </aside>}
      </div>
    </main>
  );
}

/** A picked point (or an area of the search): what it is, where, and the nearest useful points. */
function PointCard({ title, kind, icon, coords, note, near, onNear, onClose, onBack, way, onWay }: {
  title: string; kind: string; icon: string | null; coords: [number, number] | null; note: string; near: Near[];
  onNear(p: Poi): void; onClose(): void; onBack: (() => void) | null; way?: Way | null; onWay?(way: Way): void;
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
      {way && onWay && zones[way.to] && (
        <button className="btn primary map-near-btn" onClick={() => onWay(way)}><IconNavigate /> Перейти: {zones[way.to].name}</button>
      )}
      {onBack && <button className="btn map-clear" onClick={onBack}>К метке из чата</button>}
      <NearList near={near} onNear={onNear} />
    </div>
  );
}

/**
 * An NPC or a monster found by the search or opened from a card: its points in this zone (several when it stands in
 * several places), the chosen one centred and ringed on the map. A floor is not known for points of a dungeon with
 * floors (the client gives no height bounds): they are shown on every floor, and the card says so.
 */
function NpcCard({ npc, zone, near, onPoint, onNear, onClose }: {
  npc: { name: string; points: SpawnPoint[]; at: number; npc: string }; zone: Zone; near: Near[];
  onPoint(i: number): void; onNear(p: Poi): void; onClose(): void;
}) {
  const [gx, gy] = npc.points[npc.at];
  const kind = npc.npc.startsWith("poi:") ? "Точка карты" : "НПС / монстр";
  return (
    <div className="map-card">
      <div className="map-card-head">
        <div className="map-point-title">
          <span className="map-npc-badge" aria-hidden="true" />
          <div><span className="muted">{kind} · {zone.name}</span><h2>{npc.name}</h2></div>
        </div>
        <button className="x" aria-label="Закрыть" onClick={onClose}><IconClose /></button>
      </div>
      <div className="muted map-xy">x {Math.round(gx)} · y {Math.round(gy)}</div>
      {zone.layers.length > 1 && <p className="map-note">Этаж в данных клиента не указан: точки показаны на всех этажах.</p>}
      {npc.points.length > 1 && (
        <>
          <h3 className="map-near-title">Точки в зоне: {npc.points.length}</h3>
          <ul className="map-near map-npc-points">
            {npc.points.slice(0, 40).map(([x, y], i) => (
              <li key={i}><button className={i === npc.at ? "on" : ""} aria-current={i === npc.at} onClick={() => onPoint(i)}>
                <span className="map-npc-dot" aria-hidden="true" />
                <span className="t"><b>Точка {i + 1}</b><span>x {Math.round(x)} · y {Math.round(y)}</span></span>
                <IconChevron open={false} />
              </button></li>
            ))}
          </ul>
          {npc.points.length > 40 && <p className="map-note">Показаны первые 40 из {npc.points.length}.</p>}
        </>
      )}
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
