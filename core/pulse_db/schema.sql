-- The schema of data/pulse.db: one game database for every tab of Pulse+ (docs/ADR-002-pulse-db.md).
-- The builder (core/pulse_db/build.py) and the launcher's tests (launcher/src/core/db) both read this file.
-- Rules: the key is the client's id as text; links are ids only; NULL is «not known»; every row has a source;
-- derived values (the search key, flags) are made by the build, never by the program.

CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value NOT NULL                 -- text; «spec_dict» is a BLOB, the dictionary of item.spec
);

-- every NPC and monster any source knows; a marker of the map's own («poi:Имя») is an NPC of source «map»
CREATE TABLE npc (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  name_key TEXT NOT NULL,        -- lower case, «ё» as «е»: for search
  kind TEXT,                     -- «Монстр», «Торговец», «Стражник» …
  rank TEXT,                     -- «Обычный», «Элитный», «Героический», «Легендарный»
  level INTEGER,
  race TEXT,
  faction TEXT,
  role TEXT,                     -- merchant, teleport, warehouse … (the client's function)
  icon TEXT,                     -- a picture of data/bestiary/icons
  deco INTEGER NOT NULL DEFAULT 0,     -- decorative: no function, no quest (the map's small blue dots)
  sp_only INTEGER NOT NULL DEFAULT 0,  -- known only by the client's spawn groups: may appear on a condition
  source TEXT NOT NULL,          -- bestiary | client | map | own
  -- the bestiary's card (stage 2): who is listed in the «NPC / Бестиарий» tab and what its card shows
  listed INTEGER NOT NULL DEFAULT 0,   -- a record of the bestiary (the tab lists these)
  category TEXT,                 -- monster | npc
  internal_name TEXT,
  title TEXT,                    -- «Торговая компания …»
  description TEXT,              -- the service, «Продаёт предметы.»
  search_text TEXT NOT NULL DEFAULT '',  -- every name and the id, lower case: the tab's search
  sort_key TEXT NOT NULL DEFAULT '',     -- the Russian order of the name (lower case, «ё» as «е»)
  zone_names TEXT NOT NULL DEFAULT '',
  hp_bar INTEGER,                -- the HP artwork's rank 1…4
  has_profile INTEGER NOT NULL DEFAULT 0,
  service INTEGER NOT NULL DEFAULT 0,  -- technical and duplicate records: a group of their own
  point_count INTEGER NOT NULL DEFAULT 0,  -- the NPC's points in npc_point (its aliases' too): the same count the map shows
  drop_count INTEGER NOT NULL DEFAULT 0,
  drops BLOB,                    -- the item ids it drops (the knowledge base's list) in the card's order, packed (see below)
  profile TEXT                   -- the rest of the card as JSON: stats, kb_locations, kb_url, kb_status, trade_tabs …
);
CREATE INDEX npc_name_key ON npc (name_key);
CREATE INDEX npc_listed ON npc (listed, service);

-- another id the same NPC goes by: a marker of the map («poi:Имя») is the NPC of that name
CREATE TABLE npc_alias (
  alias TEXT NOT NULL,
  npc_id TEXT NOT NULL,
  PRIMARY KEY (alias, npc_id)
);
CREATE INDEX npc_alias_npc ON npc_alias (npc_id);

-- every point of every NPC: the map's (spawns.json), the game data's (npc_points), the bestiary's own; one place once
CREATE TABLE npc_point (
  npc_id TEXT NOT NULL,
  map_id TEXT NOT NULL,
  x REAL NOT NULL,               -- game coordinates, as the map's toImage takes them
  y REAL NOT NULL,
  z REAL NOT NULL DEFAULT 0,
  source TEXT NOT NULL           -- map | client | bestiary
);
CREATE INDEX npc_point_npc ON npc_point (npc_id);
CREATE INDEX npc_point_map ON npc_point (map_id);

-- every item any source knows, once (stage 3): the names of chat links (item_names.tsv), the catalog of item cards
-- (watch_items.csv, its fields win), their descriptions (item_specs.json.gz) and the bestiary's drops
CREATE TABLE item (
  id INTEGER PRIMARY KEY,        -- the client's item id (a number: the drop links below stay small)
  name TEXT NOT NULL,
  name_key TEXT NOT NULL,
  level INTEGER,
  category TEXT,                 -- the list's group: «Лата», «Оружие» … «Припасы», «Прочее»
  grade TEXT,                    -- junk | common | rare | legend | unique | epic | mythic
  kind TEXT,                     -- finer type for the filter: «Меч», «Кольца»
  icon TEXT,                     -- a picture of data/icons (without «.png»), the catalog's
  drop_icon TEXT,                -- a picture of data/bestiary/icons/items, the bestiary's
  catalog_ord INTEGER,           -- the place in the catalog (it has a card); NULL: only a name
  spec BLOB,                     -- the card's description, JSON {name, grade, blocks}, deflated with meta «spec_dict»
  dropped_by BLOB                -- the NPC ids that drop it, sorted, packed as steps (see below)
);
CREATE INDEX item_name_key ON item (name_key);
CREATE INDEX item_catalog ON item (catalog_ord) WHERE catalog_ord IS NOT NULL;

-- The drops are 2.5 million NPC → item links read on exactly two paths: an NPC's card (npc.drops) and the NPCs found by
-- a dropped item (item.dropped_by). They are kept as packed id lists there (~14 MB) rather than as a link table with its
-- index (~74 MB): 7 bits an id byte, low bits first, the high bit set while more bytes follow (core/pulse_db/build.py
-- pack_ids, launcher/src/core/db/packed.ts). The client's own drop tables come in stage 4.

-- what a merchant sells, in the card's order
CREATE TABLE npc_stock (
  npc_id TEXT NOT NULL,
  ord INTEGER NOT NULL,
  item_id TEXT,
  name TEXT NOT NULL,
  name_key TEXT NOT NULL,
  rarity TEXT,
  level TEXT,
  icon TEXT,                     -- a picture of data/bestiary/icons («client/icon_item_….png»)
  grp TEXT,                      -- the trade tab's group, «Бакалея»
  trade_mode TEXT,               -- «Покупка», «Обмен» …
  PRIMARY KEY (npc_id, ord)
);

-- the zones and the named regions an NPC stands in, and its approximate spawn areas (the bestiary's)
CREATE TABLE npc_zone (npc_id TEXT NOT NULL, map_id TEXT NOT NULL, name TEXT NOT NULL);
CREATE INDEX npc_zone_npc ON npc_zone (npc_id);
CREATE TABLE npc_region (npc_id TEXT NOT NULL, map_id TEXT NOT NULL, name TEXT NOT NULL);
CREATE INDEX npc_region_npc ON npc_region (npc_id);
CREATE TABLE npc_area (
  npc_id TEXT NOT NULL, map_id TEXT NOT NULL, area_id TEXT NOT NULL, point_count INTEGER NOT NULL,
  center_x REAL, center_y REAL, names TEXT NOT NULL, polygon TEXT NOT NULL  -- JSON lists
);
CREATE INDEX npc_area_npc ON npc_area (npc_id);

-- stage 4: the game data's quests, recipes and vendors (core/game_data, data/game). The client's drop list is not a
-- table of its own: it is a part of the bestiary's (npc.drops / item.dropped_by hold every one of its 1.4 million links).

-- every quest: the game data's, and the names of chat links (quest_names.tsv) for the rest
CREATE TABLE quest (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  name_key TEXT NOT NULL,
  min_level INTEGER,
  max_level INTEGER,             -- 0: no upper limit
  race TEXT,                     -- «pc_light», «pc_dark» or both, comma-separated
  category TEXT,                 -- «quest | Элтнен»
  repeatable INTEGER,
  giver TEXT,                    -- the NPC that gives it (npc.id), NULL when not known
  ender TEXT,                    -- the NPC that takes it back
  rewards TEXT                   -- JSON [{type, group, item, amount}]
);
CREATE INDEX quest_giver ON quest (giver);
CREATE INDEX quest_ender ON quest (ender);
CREATE INDEX quest_name_key ON quest (name_key);

-- the crafting recipes and their parts, in the recipe's order
CREATE TABLE recipe (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  name_key TEXT NOT NULL,
  product INTEGER,               -- item.id of what it makes
  count INTEGER,                 -- how many it makes
  profession TEXT,               -- weaponsmith | armorsmith | tailoring | handiwork | alchemy | cooking | convert
  level INTEGER,
  race TEXT,
  combo TEXT                     -- JSON list of the item ids a critical success may make instead
);
CREATE INDEX recipe_product ON recipe (product);
CREATE TABLE recipe_part (
  recipe_id INTEGER NOT NULL,
  ord INTEGER NOT NULL,
  item_id INTEGER NOT NULL,
  count INTEGER NOT NULL,
  PRIMARY KEY (recipe_id, ord)
);
CREATE INDEX recipe_part_item ON recipe_part (item_id);

-- what an NPC trades by the client's lists (the bestiary's goods with groups and names are npc_stock)
CREATE TABLE vendor_item (
  npc_id TEXT NOT NULL,
  item_id INTEGER NOT NULL,
  kind TEXT NOT NULL             -- trade_info | abyss_trade_info | extra_currency_trade_info | trade_in_trade_info | coupon_trade_info
);
CREATE INDEX vendor_item_npc ON vendor_item (npc_id);
CREATE INDEX vendor_item_item ON vendor_item (item_id);

-- the titles: empty until the client's titles are exported (meta «title» says «not built»)
CREATE TABLE title (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  name_key TEXT NOT NULL,
  description TEXT,
  race TEXT,
  stats TEXT                     -- JSON
);
