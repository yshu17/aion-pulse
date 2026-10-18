"""Download only unique ready-made NPC/drop icons referenced by cached Aion Empire KB records."""
from __future__ import annotations
import json
import re
import shutil
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

BASE="https://kb.aionempire.com"
UA="Aion Chat Watcher local data preparation (human-requested)"


def cached_rows(path: Path):
    """Stream a growing cache without loading every profile/drop into memory."""
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                if not line.endswith("\n"):
                    return
                raise


def fetch(url: str) -> bytes:
    req=urllib.request.Request(url,headers={"User-Agent":UA})
    with urllib.request.urlopen(req,timeout=30) as r:
        return r.read()


def main():
    root=Path(".")
    cache=root/"downloads/aion_kb_bestiary/npc_profiles.jsonl"
    catalog=root/"downloads/aion_kb_bestiary/catalog_pages.jsonl"
    assets={}
    if catalog.exists():
        for row in cached_rows(catalog):
            for entry in row.get("entries",[]):
                path=entry.get("icon","")
                if path.startswith("/assets/images/npc/"):
                    assets[("npc",Path(path).name)]=path
    if cache.exists():
        for row in cached_rows(cache):
            if row.get("error"):
                continue
            path=row.get("icon","")
            if path.startswith("/assets/images/npc/"):
                assets[("npc",Path(path).name)]=path
            for drop in row.get("drops",[]):
                path=drop.get("icon","")
                if path.startswith("/assets/images/icons/"):
                    assets[("items",Path(path).name)]=path
    pending=[]
    for (kind,name),path in sorted(assets.items()):
        src=BASE+path
        dl=root/"downloads/aion_kb_bestiary/icons"/kind/name
        app=root/"local/bestiary/icons"/kind/name
        pending.append((src,dl,app))
    lock=Lock()
    errors=[]
    def one(args):
        src,dl,app=args
        if dl.exists() and dl.stat().st_size>0:
            data=dl.read_bytes()
        elif app.exists() and app.stat().st_size>0:
            data=app.read_bytes()
        else:
            last=None
            for attempt in range(4):
                try:
                    data=fetch(src); break
                except (OSError,urllib.error.URLError,TimeoutError) as e:
                    last=str(e);time.sleep(0.7*(attempt+1))
            else:
                return (src,last or "failed")
        dl.parent.mkdir(parents=True,exist_ok=True)
        app.parent.mkdir(parents=True,exist_ok=True)
        dl.write_bytes(data)
        app.write_bytes(data)
        return None
    print("unique icons",len(pending),flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i,f in enumerate(as_completed([pool.submit(one,x) for x in pending]),1):
            err=f.result()
            if err: errors.append(err)
            if i%200==0: print(f"icon progress {i}/{len(pending)}",flush=True)
    print(f"saved={len(pending)-len(errors)} failed={len(errors)}",flush=True)
    if errors:
        Path("downloads/aion_kb_bestiary/icon_errors.json").write_text(json.dumps(errors,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__": main()
