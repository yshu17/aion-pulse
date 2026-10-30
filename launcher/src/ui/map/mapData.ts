// The map's data for the screen: zones (data/maps/maps.json + labels.tsv), points (poi.json), their icons (the game's
// own map and radar sprites, as Pulse draws them) and the zone pictures. The pictures (44 MB) are read from data/maps
// next to the program, not built into it; the plain browser (the dev page) takes them from the dev server.
import labelsText from "../../../../data/maps/labels.tsv?raw";
import mapsJson from "../../../../data/maps/maps.json?raw";
import poiJson from "../../../../data/maps/poi.json?raw";
import { PoiStore } from "../../core/map/poi";
import { parseZones, toImage, Zone } from "../../core/map/zones";
import { mapNames } from "../data";
import { platform } from "../platform";

export const zones: Record<string, Zone> = parseZones(mapsJson, labelsText, mapNames, () => true);
export const poi: PoiStore = PoiStore.load(poiJson).projected(
  Object.fromEntries(Object.entries(zones).map(([id, zone]) => [id, (gx: number, gy: number) => toImage(zone, gx, gy)])));

const icons = import.meta.glob("../../../../data/maps/icons/*.png", { query: "?url", import: "default", eager: true }) as Record<string, string>;

/** URL of a map icon file (poi.json types name it, e.g. «teleport.png»), or null. */
export function iconUrl(file: string | undefined): string | null {
  return file ? icons[`../../../../data/maps/icons/${file}`] ?? null : null;
}

export const typeIcon = (type: string) => iconUrl((poi.types[type]?.icon as string | undefined) ?? undefined);
export const PLACE_ICON = iconUrl("place.png"); // the blue cross of a place from the chat, as the game's map

// the dev page only: the pictures come from the dev server (this list is dropped from the program's build)
const devPictures = import.meta.env.DEV
  ? import.meta.glob("../../../../data/maps/client/*.jpg", { query: "?url", import: "default" }) as Record<string, () => Promise<string>>
  : {};

const pictures = new Map<string, Promise<string | null>>();
let mapsDir: Promise<string | null> | null = null;

async function readPicture(file: string): Promise<string | null> {
  if (platform === null) {
    const load = devPictures[`../../../../data/maps/${file}`];
    return load ? await load() : null;
  }
  mapsDir ??= platform.mapsDir().catch(() => null);
  const dir = await mapsDir;
  if (!dir) return null;
  const path = `${dir}\\${file.replace(/\//g, "\\")}`;
  const size = await platform.fileSize(path);
  const bytes = await platform.readRange(path, 0, size);
  return URL.createObjectURL(new Blob([bytes.slice()], { type: "image/jpeg" }));
}

/** The URL of a zone picture (read once), or null when it is not there. */
export function pictureUrl(file: string): Promise<string | null> {
  let url = pictures.get(file);
  if (!url) {
    url = readPicture(file).catch(() => null);
    pictures.set(file, url);
    url.then((got) => { if (got === null) pictures.delete(file); }); // missing now: try again next time
  }
  return url;
}
