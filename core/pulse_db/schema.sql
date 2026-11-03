-- The schema of data/pulse.db: one game database for every tab of Pulse+ (docs/ADR-002-pulse-db.md).
-- The builder (core/pulse_db/build.py) and the launcher's tests (launcher/src/core/db) both read this file.
-- Rules: the key is the client's id as text; links are ids only; NULL is «not known»; every row has a source;
-- derived values (the search key, flags) are made by the build, never by the program.

CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
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
  source TEXT NOT NULL           -- bestiary | client | map | own
);
CREATE INDEX npc_name_key ON npc (name_key);

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
