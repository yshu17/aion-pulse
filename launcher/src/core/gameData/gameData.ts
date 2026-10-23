/**
 * The game data of Pulse+: the folder data/game built by tools/build_game_data.py (format: core/DATA.md, «Game data»).
 *
 *     const data = new GameData(fetchFile, drops);         // how files are read and how drops are asked: parameters
 *     (await data.manifest())?.sections.items.records
 *     (await data.byId("items")).get("100000001")?.name   // a section is loaded on the first use and kept
 *     await data.table("vendors")                         // { columns, rows } for the big tables
 *     await data.dropsOfNpc("210065")                     // from drops.sqlite through the program (Rust), [] in a browser
 *
 * IDs are strings, an unknown value is null, a missing record means «not checked». A missing or broken file reads as
 * empty data, never as an error. No path, no timer, no window here: the caller gives the file reader.
 */

export const SCHEMA = 1;

export const SECTION_FILES = {
  items: "items.json.gz",
  recipes: "recipes.json.gz",
  npcs: "npcs.json.gz",
  maps: "maps.json",
  labels: "labels.json.gz",
  npc_points: "npc_points.json.gz",
  vendors: "vendors.json.gz",
  quests: "quests.json.gz",
  skills: "skills.json.gz",
  stigmas: "stigmas.json",
  classes: "classes.json",
} as const;
export const MANIFEST = "manifest.json";

export type Section = keyof typeof SECTION_FILES;
export type Source = "client" | "site";

export interface Item {
  id: string;
  name: string | null;
  type: string | null;
  weapon: string | null;
  armor: string | null;
  level: number | null;
  price: number | null;
  icon: string | null;
  category: string | null;
  grade: string | null;
  source: Source;
  name_source?: "legacy"; // the name is from the older item_names.tsv, the client strings have none
}

export interface Recipe {
  id: string;
  name: string | null;
  product: string | null;
  count: number | null;
  profession: string | null;
  level: number | null;
  race: string | null;
  ingredients: [string, number][];
  combo: string[] | null;
  source: Source;
}

export interface Npc {
  id: string;
  name: string | null;
  function: string | null;
  ui: string | null;
  tribe: string | null;
  race: string | null;
  source: Source;
}

export interface MapInfo {
  id: string;
  name: string | null;
  file: string | null;
  size: number | null;
  side: string | null;
}

export interface Reward {
  type: string | null;
  group: string | null;
  item: string | null;
  amount: number | null;
}

export interface Quest {
  id: string;
  name: string | null;
  min_level: number | null;
  max_level: number | null; // 0: no limit
  race: string[] | null;
  category: string | null;
  repeatable: boolean | null;
  giver: string | null;
  ender: string | null;
  rewards: Reward[];
}

export interface Skill {
  id: string;
  name: string | null;
  classes: string[] | null;
  level: number | null;
  kind: string | null;
  mp: number | null;
  cooldown_ms: number | null;
  cast_ms: number | null;
  range: number | null;
  requires: string | null;
  source: Source;
}

export interface SkillLearn {
  id: string;
  skill: string | null;
  class: string | null;
  race: string | null;
  level: number | null;
  stigma: number | null;
}

export interface Stigma {
  type: string | null; // «skill» or «slot»
  skill: string | null;
  class: string | null;
  level: number | null;
  slot: number | null;
  rank: number | null;
  rank_max: number | null;
  requires: string | null;
}

export interface ClassInfo {
  id: string; // «ASSASSIN.PC_DARK»
  class: string;
  race: string | null;
  name: string | null;
  base_stats: Record<string, number> | null; // null until the client table is found
  per_level: Record<string, number> | null;
  source: Source;
}

export interface Table {
  columns: string[];
  rows: (string | number | null)[][];
}

/** The records of each record section. */
export interface Records {
  items: Item;
  recipes: Recipe;
  npcs: Npc;
  maps: MapInfo;
  quests: Quest;
  stigmas: Stigma;
  classes: ClassInfo;
}
export type RecordSection = keyof Records;
export type IdSection = Exclude<RecordSection, "stigmas">; // stigma rules have no ID of their own
export type TableSection = "labels" | "npc_points" | "vendors";

export interface Manifest {
  schema: number;
  built: string | null;
  client_build: string | null;
  sections: Record<string, { file: string; records: number; sha256: string }>;
}

export interface Drop {
  npc_id: number;
  item_id: number;
  chance_min: number | null;
  chance_max: number | null;
  count_min: number | null;
  count_max: number | null;
}

/** Bytes of a file of the data folder, or null when it is not there. */
export type FileReader = (file: string) => Promise<Uint8Array | null>;

/** The drops live in SQLite: the program asks them (Rust); a browser has none. */
export interface DropsSource {
  ofNpc(npcId: string): Promise<Drop[]>;
  droppers(itemId: string): Promise<Drop[]>;
}

/** gzip-compressed or plain JSON bytes into a value; null when the bytes are not that. A «.gz» file that a web server
 * already unpacked on the way (Content-Encoding) is read as plain JSON. */
export async function decodeJson(bytes: Uint8Array, gzipped: boolean): Promise<unknown> {
  const plain = () => JSON.parse(new TextDecoder().decode(bytes));
  try {
    if (!gzipped) return plain();
    const isGzip = bytes[0] === 0x1f && bytes[1] === 0x8b;
    if (!isGzip) return plain();
    const stream = new Blob([bytes as BlobPart]).stream().pipeThrough(new DecompressionStream("gzip"));
    return JSON.parse(await new Response(stream).text());
  } catch {
    return null;
  }
}

const isObject = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

export class GameData {
  private sections = new Map<Section, Promise<Record<string, unknown>>>();
  private indexes = new Map<IdSection, Map<string, unknown>>();
  private manifestValue: Promise<Manifest | null> | null = null;

  constructor(private read: FileReader, private drops: DropsSource | null = null) {}

  /** The manifest, or null when the folder is not built or has a schema this reader does not know. */
  manifest(): Promise<Manifest | null> {
    this.manifestValue ??= this.load(MANIFEST).then((value) => (isObject(value) && value.schema === SCHEMA ? (value as unknown as Manifest) : null));
    return this.manifestValue;
  }

  private async load(file: string): Promise<unknown> {
    try {
      const bytes = await this.read(file);
      return bytes ? await decodeJson(bytes, file.endsWith(".gz")) : null;
    } catch {
      return null;
    }
  }

  /** The whole section object ({schema, section, ...}); {} when it is not built or broken. */
  section(name: Section): Promise<Record<string, unknown>> {
    let pending = this.sections.get(name);
    if (!pending) {
      pending = this.load(SECTION_FILES[name]).then((value) => (isObject(value) && value.schema === SCHEMA ? value : {}));
      this.sections.set(name, pending);
    }
    return pending;
  }

  async records<K extends RecordSection>(name: K): Promise<Records[K][]> {
    const section = await this.section(name);
    return Array.isArray(section.records) ? (section.records as Records[K][]) : [];
  }

  /** The records of a section by ID (built once). */
  async byId<K extends IdSection>(name: K): Promise<Map<string, Records[K]>> {
    const ready = this.indexes.get(name);
    if (ready) return ready as Map<string, Records[K]>;
    const index = new Map((await this.records(name)).map((record) => [record.id, record] as const));
    this.indexes.set(name, index);
    return index;
  }

  async table(name: TableSection): Promise<Table> {
    const section = await this.section(name);
    return {
      columns: Array.isArray(section.columns) ? (section.columns as string[]) : [],
      rows: Array.isArray(section.rows) ? (section.rows as Table["rows"]) : [],
    };
  }

  async skills(): Promise<{ skills: Skill[]; learns: SkillLearn[] }> {
    const section = await this.section("skills");
    return { skills: Array.isArray(section.skills) ? (section.skills as Skill[]) : [], learns: Array.isArray(section.learns) ? (section.learns as SkillLearn[]) : [] };
  }

  /** What an NPC drops. [] also when the NPC was not checked: the drops are not a complete list. */
  async dropsOfNpc(npcId: string): Promise<Drop[]> {
    if (!this.drops || !/^\d+$/.test(npcId)) return [];
    try { return await this.drops.ofNpc(npcId); } catch { return []; }
  }

  /** Who drops an item. */
  async droppersOf(itemId: string): Promise<Drop[]> {
    if (!this.drops || !/^\d+$/.test(itemId)) return [];
    try { return await this.drops.droppers(itemId); } catch { return []; }
  }
}
