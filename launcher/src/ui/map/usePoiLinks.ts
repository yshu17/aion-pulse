// The links of a picked map point (core/db/poiLinks.ts) read from pulse.db: its NPC for «NPC» and the quests of its note.
import { useEffect, useState } from "react";

import { poiLinks, questNote, type PoiLinks } from "../../core/db/poiLinks";
import { pulseDb } from "../db/pulseDb";

const NONE: PoiLinks = { npc: null, quests: {} };

/** The point's links; nothing while pulse.db answers or when there is no database. */
export function usePoiLinks(name: string, mapId: string, note: string): PoiLinks {
  const [links, setLinks] = useState<PoiLinks>(NONE);
  useEffect(() => {
    setLinks(NONE);
    if (!name) return;
    let alive = true;
    const names = questNote(note)?.names ?? [];
    pulseDb().then((all) => (all ? poiLinks(all, name, mapId, names) : NONE))
      .then((got) => { if (alive) setLinks(got); }).catch(() => {});
    return () => { alive = false; };
  }, [name, mapId, note]);
  return links;
}
