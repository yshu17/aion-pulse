/**
 * The map's view and the right-hand card, without a screen — the rules of Pulse's watcher/mapview.py and mapcard.py:
 * how far it zooms, how the picture is kept on screen, the size of the icons, game coordinates under the mouse, the
 * points shown for a side and a filter, and the nearest useful points («Рядом»). Pure: numbers in, numbers out.
 *
 * A view is { zoom, left, top }: screen px per picture px, and the picture px at the view's left and top edges.
 */

import { pyHypot } from "../py";
import { Poi, PoiStore } from "./poi";
import { FILTER_GROUPS, QUEST_TYPES, SHOWN_TYPES, unturnPoint, Zone } from "./zones";

export interface View { zoom: number; left: number; top: number }

export const MAX_ZOOM = 4.0; // screen px per picture px
export const ZOOM_STEP = 1.25;
export const BIG_TYPES = new Set(["teleport", "bindstone"]); // drawn larger than the rest
// landmarks drawn larger: siege fortresses and the Silentera tunnel +85 %, dungeon entrances +50 %, artifacts +25 %
export const ICON_SCALE: Record<string, number> = { fortress: 1.85, tunnel: 1.85, dungeon: 1.5, artifact: 1.25 };
export const LABELS_MIN_WIDTH = 1300; // px the zone takes on screen before area names are drawn
export const LABELS_ZOOM_WIDTH = 4000; // px before the «zoom» names (camps, gates, small places) are drawn too
export const NEARBY_TYPES = ["teleport", "bindstone", "warehouse", "merchant", "stigma", "artifact"];

/** The zoom at which the whole zone fits the smaller side of the view. */
export function fitZoom(zone: Zone, width: number, height: number): number {
  return Math.min(width, height) / zone.size;
}

/**
 * Keep the picture on screen. Smaller than the view (along an axis): it moves freely while it stays whole inside;
 * larger: it may go half a view past its edge, so a point at the very edge can still be put in the centre.
 */
export function clampView(view: View, zone: Zone, width: number, height: number): View {
  const axis = (start: number, viewLen: number) => {
    const size = zone.size;
    if (viewLen >= size) return Math.min(Math.max(start, size - viewLen), 0);
    return Math.min(Math.max(start, -viewLen / 2), size - viewLen + viewLen / 2);
  };
  return { zoom: view.zoom, left: axis(view.left, width / view.zoom), top: axis(view.top, height / view.zoom) };
}

/** The whole zone, centred. */
export function fitView(zone: Zone, width: number, height: number): View {
  const zoom = fitZoom(zone, width, height);
  return clampView({ zoom, left: (zone.size - width / zoom) / 2, top: (zone.size - height / zoom) / 2 }, zone, width, height);
}

/** A new zoom (kept between the fit and MAX_ZOOM) with the picture point under (sx, sy) staying there. */
export function zoomAt(view: View, zoom: number, sx: number, sy: number, zone: Zone, width: number, height: number): View {
  const z = Math.max(fitZoom(zone, width, height), Math.min(MAX_ZOOM, zoom));
  const ix = view.left + sx / view.zoom;
  const iy = view.top + sy / view.zoom;
  return clampView({ zoom: z, left: ix - sx / z, top: iy - sy / z }, zone, width, height);
}

/** The view with a picture point in its centre (the zoom stays). */
export function centreOn(view: View, ix: number, iy: number, zone: Zone, width: number, height: number): View {
  return clampView({ zoom: view.zoom, left: ix - width / 2 / view.zoom, top: iy - height / 2 / view.zoom }, zone, width, height);
}

export const toScreen = (view: View, ix: number, iy: number): [number, number] =>
  [(ix - view.left) * view.zoom, (iy - view.top) * view.zoom];

/** Game coordinates of a picture point (the inverse of toImage), null for a zone without a transform. */
export function toGame(zone: Zone, ix: number, iy: number): [number, number] | null {
  if (!zone.kx[0] || !zone.ky[0]) return null;
  const [ux, uy] = unturnPoint(zone.size, zone.turn ?? 0, ix, iy);
  return [(uy - zone.ky[1]) / zone.ky[0], (ux - zone.kx[1]) / zone.kx[0]];
}

/** Game coordinates under a screen point, null for a zone without a transform. */
export function gameAt(view: View, zone: Zone, sx: number, sy: number): [number, number] | null {
  return toGame(zone, view.left + sx / view.zoom, view.top + sy / view.zoom);
}

/** Types drawn at one size whatever the zoom: the spatial rifts, as small as the tunnel icon of the filter menu (22 px) +25 %. */
export const FIXED_SIZE: Record<string, number> = { direct_portal: 28 };

/** Icon px for a zoom: big enough to read on the whole map, teleporters bigger, landmarks scaled. */
export function iconSize(type: string, zoom: number): number {
  if (type in FIXED_SIZE) return FIXED_SIZE[type];
  let size = Math.max(28, Math.min(40, Math.round(22 + 8 * zoom)));
  if (BIG_TYPES.has(type)) size += 8;
  return Math.round(size * (ICON_SCALE[type] ?? 1.0));
}

/** Which area names are drawn at a zoom: none while the zone is small on screen, the «zoom» ones only up close. */
export function labelLevels(zone: Zone, zoom: number): Set<string> {
  const width = zoom * zone.size;
  if (width < LABELS_MIN_WIDTH) return new Set();
  return new Set(width >= LABELS_ZOOM_WIDTH ? ["main", "zoom"] : ["main"]);
}

/** The point types drawn with some filter groups switched off. */
export function shownTypes(store: PoiStore, hiddenGroups: Iterable<string>): Set<string> {
  const hidden = new Set<string>();
  for (const group of hiddenGroups) for (const type of FILTER_GROUPS[group]?.[1] ?? []) hidden.add(type);
  return new Set([...SHOWN_TYPES, ...QUEST_TYPES].filter((t) => !hidden.has(t) && t in store.types));
}

export interface Near { type: string; typeName: string; poi: Poi; metres: number }

/** The closest teleporter, kisk, warehouse, merchant, stigma master and artifact around a game position. */
export function nearby(store: PoiStore, zone: string, gx: number, gy: number, side: string, layer: number | null,
                       exclude: Poi | null = null): Near[] {
  const out: Near[] = [];
  for (const type of NEARBY_TYPES) {
    let best: Poi | null = null;
    let bestMetres = Infinity;
    for (const p of store.inZone(zone, new Set([type]), side, layer)) {
      if (p === exclude) continue;
      const metres = pyHypot(p.gx - gx, p.gy - gy);
      if (metres < bestMetres) { best = p; bestMetres = metres; }
    }
    if (best) out.push({ type, typeName: store.typeName(type), poi: best, metres: bestMetres });
  }
  return out;
}

/** The zones of a side, by name: the ones both sides share and that side's own. */
export function zonesOfSide(zones: Record<string, Zone>, side: string): Zone[] {
  return Object.values(zones).filter((z) => z.side === "" || z.side === side).sort((a, b) => a.name.localeCompare(b.name, "ru"));
}
