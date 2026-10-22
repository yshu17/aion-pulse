import { useEffect, useState } from "react";

import { iconUrl } from "./data";

/** An item picture from data/icons (the same files Pulse shows); a quiet square while it loads or when missing. */
export function Icon({ name, size = 40 }: { name: string; size?: number }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    iconUrl(name.replace(/\.png$/, "")).then((u) => { if (alive) setUrl(u); });
    return () => { alive = false; };
  }, [name]);
  const style = { width: size, height: size };
  return url ? <img className="icon" src={url} style={style} alt="" /> : <span className="icon blank" style={style} />;
}
