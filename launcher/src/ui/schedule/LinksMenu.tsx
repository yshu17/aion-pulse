import { useEffect, useRef, useState } from "react";

import { IconClose, IconLink, IconPlus } from "../icons";
import type { Boot } from "../useBoot";
import { BUILT_IN_LINK, LINKS_FILE, linkName, parseLinks, SavedLink, webAddress } from "./links";

/** The link button next to «Проверить обновление»: a small menu with the links to open and a form for a new one. */
export function LinksMenu({ boot }: { boot: Boot }) {
  const files = boot.platform;
  const path = boot.ownFile(LINKS_FILE);
  const [open, setOpen] = useState(false);
  const [saved, setSaved] = useState<SavedLink[]>([]);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [error, setError] = useState("");
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!files || !path) return;
    files.readText(path).then((text) => setSaved(parseLinks(text))).catch(() => {});
  }, [files, path]);

  useEffect(() => { // a press outside the menu or Esc closes it
    if (!open) return;
    const outside = (e: Event) => { if (!root.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("pointerdown", outside);
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("pointerdown", outside); window.removeEventListener("keydown", esc); };
  }, [open]);

  const store = (next: SavedLink[]) => {
    setSaved(next);
    if (files && path) files.writeText(path, JSON.stringify(next, null, 1) + "\n").catch(() => {});
  };

  const add = () => {
    const url = webAddress(address);
    if (url === null) {
      setError("Адрес должен начинаться с https:// или http://");
      return;
    }
    store([...saved, { name: linkName(name, url), url }]);
    setName("");
    setAddress("");
    setError("");
  };

  const openLink = (url: string) => {
    if (files) files.openUrl(url).catch(() => {});
    else window.open(url, "_blank");
    setOpen(false);
  };

  return (
    <div className="sch-links" ref={root}>
      <button className={`btn sch-linkbtn${open ? " on" : ""}`} aria-label="Ссылки" aria-expanded={open} title="Ссылки: статья расписания и свои"
        onClick={() => setOpen(!open)}><IconLink /></button>
      {open && (
        <div className="sch-linkmenu" role="menu">
          {[BUILT_IN_LINK, ...saved].map((link, i) => (
            <div key={`${i}${link.url}`} className="row">
              <button role="menuitem" className="go" title={link.url} onClick={() => openLink(link.url)}>{link.name}</button>
              {i > 0 && (
                <button className="x" aria-label={`Удалить ссылку «${link.name}»`} title="Удалить" onClick={() => store(saved.filter((_, j) => j !== i - 1))}>
                  <IconClose />
                </button>
              )}
            </div>
          ))}
          <form className="add" onSubmit={(e) => { e.preventDefault(); add(); }}>
            <input className="inp" placeholder="Название" value={name} maxLength={60} aria-label="Название ссылки"
              onChange={(e) => setName(e.target.value)} />
            <input className={`inp${error ? " bad" : ""}`} placeholder="https://…" value={address} aria-label="Адрес ссылки"
              aria-invalid={error !== ""} onChange={(e) => { setAddress(e.target.value); setError(""); }} />
            {error && <div className="err" role="alert">{error}</div>}
            <button className="btn primary" type="submit"><IconPlus />Добавить</button>
          </form>
        </div>
      )}
    </div>
  );
}
