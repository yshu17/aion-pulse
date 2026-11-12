import { useEffect, useState } from "react";

import { iconUrl, iconUrlNow } from "./data";

/** An item picture from data/icons (the same files Pulse shows); a quiet square while it loads or when missing. */
export function Icon({ name, size = 40 }: { name: string; size?: number }) {
  const key = name.replace(/\.png$/, "");
  const [loaded, setLoaded] = useState<{ key: string; url: string | null } | null>(null);
  const now = iconUrlNow(key); // known already: drawn in the first frame, no blank square before the picture
  useEffect(() => {
    if (now !== undefined) return;
    let alive = true;
    iconUrl(key).then((url) => { if (alive) setLoaded({ key, url }); });
    return () => { alive = false; };
  }, [key, now]);
  const url = now !== undefined ? now : loaded?.key === key ? loaded.url : null;
  const style = { width: size, height: size };
  return url ? <img className="icon" src={url} style={style} alt="" decoding="async" /> : <span className="icon blank" style={style} />;
}
