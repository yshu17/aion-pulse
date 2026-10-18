"""Prepare Aion NPC/Bestiary data from local client tables and Aion Empire KB.

The client install is read-only. KB requests are GET-only and honor robots.txt (the public
robots file allows /npc and sitemap paths). Profile data is cached as JSONL for resumability.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import http.client
import json
import math
import re
import time
import urllib.error
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from threading import Lock, local

try:
    from .build_mob_data import ZONE_MAP_IDS
except ImportError:
    from build_mob_data import ZONE_MAP_IDS

BASE = "https://kb.aionempire.com"
UA = "Aion Chat Watcher local data preparation (human-requested)"
_http = local()
SITE_MAP_IDS = {
    "poeta":"210010000", "verteron":"210030000", "eltnen":"210020000",
    "heiron":"210040000", "theobomos":"210060000", "sanctum":"110010000",
    "ishalgen":"220010000", "altgard":"220030000", "morheim":"220020000",
    "beluslan":"220040000", "brusthonin":"220050000", "pandaemonium":"120010000",
    "reshanta-lower":"400010000", "reshanta-core":"400010000",
    "reshanta-upper":"400010000", "silentera":"600010000",
}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def get_text(url: str, timeout: int = 30) -> str:
    parts = urllib.parse.urlsplit(url)
    connection = getattr(_http, "connection", None)
    if connection is None or getattr(_http, "host", None) != parts.netloc:
        if connection:
            connection.close()
        connection = http.client.HTTPSConnection(parts.netloc, timeout=timeout)
        _http.connection, _http.host = connection, parts.netloc
    try:
        connection.request("GET", urllib.parse.urlunsplit(("", "", parts.path, parts.query, "")), headers={
            "User-Agent": UA, "Cookie": "PLAY_LANG=ru", "Accept-Encoding": "gzip",
        })
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            raise urllib.error.HTTPError(url, response.status, response.reason, response.headers, None)
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            body = gzip.decompress(body)
        encoding = response.headers.get_content_charset() or "utf-8"
        return body.decode(encoding, "replace")
    except (OSError, http.client.HTTPException):
        connection.close()
        _http.connection = None
        raise


def sitemap_npc_ids() -> list[str]:
    root = ET.fromstring(get_text(BASE + "/sitemap.xml"))
    urls = [e.text.strip() for e in root.iter() if e.tag.endswith("loc") and e.text]
    ids: set[str] = set()
    for url in urls:
        if not re.search(r"/sitemap-npcs-\d+\.xml$", url):
            continue
        sm = ET.fromstring(get_text(url))
        for loc in sm.iter():
            if loc.tag.endswith("loc") and loc.text:
                m = re.search(r"/npc/(\d+)$", loc.text.strip())
                if m:
                    ids.add(m.group(1))
    return sorted(ids, key=int)


def _attrs(tag: str) -> dict[str, str]:
    return dict(re.findall(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']', tag))


def local_icon(path: str) -> str:
    if not path:
        return ""
    name = re.split(r"[/\\]", path)[-1]
    if "/assets/images/npc/" in path:
        return "npc/" + name
    if "/assets/images/icons/" in path:
        return "items/" + name
    return ""


def parse_profile(npc_id: str, page: str) -> dict:
    title = re.search(r'<div\s+class="header-title npc-name"[^>]*>(.*?)</div>', page, re.S | re.I)
    name = unescape(re.sub(r"<[^>]+>", "", title.group(1))).strip() if title else ""
    icon_match = re.search(r'<img\s+class="npc-img"\s+src="([^"]+)"', page, re.I)
    icon = icon_match.group(1) if icon_match else ""
    badges = {}
    for m in re.finditer(r'<[^>]+class="npc-badge npc-badge--(type|race|rank)"[^>]*>(.*?)</[^>]+>', page, re.S | re.I):
        badges[m.group(1)] = unescape(re.sub(r"<[^>]+>", " ", m.group(2))).strip()
    level_match = re.search(r'class="hp-bar[^\"]*bar-(\d+)[^\"]*".*?<span[^>]*>\s*(\d+)\s*</span>', page, re.S | re.I)
    level = int(level_match.group(2)) if level_match else None
    hp_bar = int(level_match.group(1)) if level_match else None
    sub = re.search(r'<div class="header-subtitle">(.*?)</div>', page, re.S | re.I)
    if sub and level is None:
        lm = re.search(r"(?:Lv\.?|Level)\s*(\d+)", re.sub(r"<[^>]+>", " ", sub.group(1)), re.I)
        if lm:
            level = int(lm.group(1))
    if level is None:
        title_level = re.search(r'<title>[^<]*\((?:Lv\.?|Ур\.?)\s*(\d+)\)', page, re.I)
        if title_level:
            level = int(title_level.group(1))
    stats = {}
    stat_re = re.compile(
        r'<div class="npc-stat">\s*<div class="npc-stat-label"[^>]*>(.*?)</div>\s*'
        r'<div class="npc-stat-value"[^>]*>(.*?)</div>', re.S | re.I)
    for m in stat_re.finditer(page):
        k = unescape(re.sub(r"<[^>]+>", " ", m.group(1))).strip()
        v = unescape(re.sub(r"<[^>]+>", " ", m.group(2))).strip()
        stats[k] = v
    drops = []
    row_re = re.compile(r'<a\s+class="npc-drop-row\s+([^"]+)"\s+href="/items/(\d+)"[^>]*>(.*?)</a>', re.S | re.I)
    for m in row_re.finditer(page):
        body = m.group(3)
        nm = re.search(r'class="npc-drop-name"[^>]*>(.*?)</span>', body, re.S | re.I)
        im = re.search(r'<img[^>]+src="([^"]+)"', body, re.I)
        drops.append({
            "item_id": m.group(2),
            "name": unescape(re.sub(r"<[^>]+>", "", nm.group(1))).strip() if nm else "",
            "rarity": m.group(1).strip(),
            "icon": im.group(1) if im else "",
            "icon_asset": local_icon(im.group(1)) if im else "",
        })
    locations = []
    loc_script = re.search(r'window\.NPC_LOCATIONS\s*=\s*(\[.*?\])\s*;', page, re.S)
    if loc_script:
        try:
            raw_locations = json.loads(loc_script.group(1))
        except json.JSONDecodeError:
            raw_locations = []
        for loc in raw_locations:
            subzones = loc.get("subzones") or []
            points = []
            for xy in loc.get("pts") or []:
                area = None
                if subzones and len(xy) >= 2:
                    candidates = [s for s in subzones if isinstance(s.get("lx"), (int, float)) and isinstance(s.get("ly"), (int, float))]
                    if candidates:
                        near = min(candidates, key=lambda s: math.hypot(xy[0] - s["lx"], xy[1] - s["ly"]))
                        area = {"id": near.get("k", ""), "name": near.get("nRu") or near.get("nEn"), "distance": round(math.hypot(xy[0]-near["lx"], xy[1]-near["ly"]), 3)}
                points.append({"x": xy[0], "y": xy[1], "area": area})
            locations.append({
                "slug": loc.get("slug", ""),
                "name": loc.get("nameRu") or loc.get("nameEn") or "",
                "faction": loc.get("faction", ""),
                "points": points,
            })
    return {
        "id": npc_id, "name": name, "level": level, "icon": icon,
        "hp_bar": hp_bar, "parser_version": 2,
        "icon_asset": local_icon(icon),
        "badges": badges, "stats": stats, "drops": drops,
        "locations": locations,
        "seller_inventory": None,
        "seller_inventory_state": "not_in_kb_profile",
        "source_url": f"{BASE}/npc/{npc_id}",
    }



def parse_catalog_page(page_number: int, page: str) -> dict:
    cards = []
    for segment in page.split('<div class="item" data-href=')[1:]:
        id_match = re.match(r'"?/npc/(\d+)"', segment)
        if not id_match:
            continue
        npc_id = id_match.group(1)
        link = re.search(r'<a class="li-i-n m10" href="/npc/\d+">(.*?)</a>', segment, re.S | re.I)
        icon = re.search(r'<img class="npc-img" src="([^"]+)"', segment, re.I)
        level = re.search(r'(?:Level|Уровень|Ур\.)\s*(\d+)', re.sub(r'<[^>]+>', ' ', segment), re.I)
        exp = re.search(r'EXP:\s*([\d,]+)', segment, re.I)
        hp = re.search(r'([\d,]+)\s*HP', segment, re.I)
        cards.append({
            "id": npc_id,
            "name": unescape(re.sub(r"<[^>]+>", "", link.group(1))).strip() if link else "",
            "level": int(level.group(1)) if level else None,
            "experience": int(exp.group(1).replace(",", "")) if exp else None,
            "hp": int(hp.group(1).replace(",", "")) if hp else None,
            "icon": icon.group(1) if icon else "",
            "source_url": f"{BASE}/npc/{npc_id}",
        })
    total_match = re.search(r'Showing\s+[\d,]+-[\d,]+\s+of\s+([\d,]+)\s+results', page, re.I)
    total = int(total_match.group(1).replace(",", "")) if total_match else None
    return {"page": page_number, "total": total, "entries": cards}


def crawl_catalog(cache_path: Path, workers: int) -> dict[str, dict]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    pages = {}
    if cache_path.exists():
        with cache_path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        if not line.endswith("\n"):
                            break  # a concurrent import has not finished its last record yet
                        raise
                    pages[int(row["page"])] = row
    first = pages.get(1)
    if not first:
        first = parse_catalog_page(1, get_text(BASE + "/npcs?p=1"))
        pages[1] = first
        with cache_path.open("a", encoding="utf-8", newline="\n") as out:
            out.write(json.dumps(first, ensure_ascii=False, separators=(",", ":")) + "\n")
    total = first.get("total") or 29808
    page_count = math.ceil(total / 20)
    pending = [i for i in range(2, page_count + 1) if i not in pages]
    print(f"KB list cache={len(pages)}/{page_count} pages; pending={len(pending)}", flush=True)
    lock = Lock()
    with cache_path.open("a", encoding="utf-8", newline="\n") as out, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(lambda n: parse_catalog_page(n, get_text(f"{BASE}/npcs?p={n}")), n): n for n in pending}
        for n, fut in enumerate(as_completed(futures), 1):
            row = fut.result()
            pages[int(row["page"])] = row
            with lock:
                out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                if n % 100 == 0:
                    out.flush()
                    print(f"KB list progress {n}/{len(pending)} pages", flush=True)
    return {entry["id"]: entry for row in pages.values() for entry in row.get("entries", [])}


def fetch_profile(npc_id: str) -> dict:
    last = None
    for attempt in range(2):
        try:
            page = get_text(f"{BASE}/npc/{npc_id}", timeout=15)
            if "header-title npc-name" not in page:
                return {"id": npc_id, "error": "profile_not_found", "parser_version": 2}
            return parse_profile(npc_id, page)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {"id": npc_id, "error": "profile_not_found", "parser_version": 2}
            last = str(exc)
            time.sleep(min(60, int(exc.headers.get("Retry-After", "2"))) if exc.headers.get("Retry-After", "2").isdigit() else 2)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError, http.client.HTTPException) as exc:
            last = str(exc)
            time.sleep(0.8 * (attempt + 1))
    return {"id": npc_id, "error": last or "fetch_failed"}


def load_cache(path: Path) -> dict[str, dict]:
    result = {}
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        if not line.endswith("\n"):
                            break
                        raise
                    if not row.get("error") or row["id"] not in result or result[row["id"]].get("error"):
                        result[row["id"]] = row
    return result


def scrape(ids: list[str], cache_path: Path, workers: int) -> dict[str, dict]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    found = load_cache(cache_path)
    pending = [i for i in ids if i not in found or found[i].get("parser_version") != 2
               or found[i].get("error") not in (None, "profile_not_found")]
    pending.sort(key=lambda npc_id: (npc_id not in found, int(npc_id)))
    print(f"KB profiles cached={len(found)}, pending={len(pending)}, workers={workers}", flush=True)
    stopped = False
    errors = []
    with cache_path.open("a", encoding="utf-8", newline="\n") as out, ThreadPoolExecutor(max_workers=workers) as pool:
        iterator = iter(pending)
        futures = {pool.submit(fetch_profile, npc_id) for npc_id in [next(iterator, None) for _ in range(workers)] if npc_id}
        n = failures = 0
        while futures:
            done, futures = wait(futures, return_when=FIRST_COMPLETED)
            for fut in done:
                row = fut.result()
                n += 1
                failed = row.get("error") not in (None, "profile_not_found")
                failures = failures + 1 if failed else 0
                if failed:
                    errors.append(row)
                if not row.get("error") or row["id"] not in found or found[row["id"]].get("error"):
                    found[row["id"]] = row
                out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                out.flush()
                if n % 100 == 0:
                    print(f"KB profile progress {n}/{len(pending)}", flush=True)
                if failures >= max(4, workers):
                    stopped = True
                npc_id = None if stopped else next(iterator, None)
                if npc_id:
                    futures.add(pool.submit(fetch_profile, npc_id))
    report = {"requested": len(ids), "complete_profiles": sum(not p.get("error") for p in found.values()),
              "stopped_on_network_errors": stopped, "remaining": sum(i not in found or found[i].get("parser_version") != 2
                      or found[i].get("error") not in (None, "profile_not_found") for i in ids), "errors": errors}
    cache_path.with_name("import-status.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "errors"}), flush=True)
    return found


def components(points: list[dict], radius: float = 90.0) -> list[list[dict]]:
    if not points:
        return []
    buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, p in enumerate(points):
        buckets[(int(p["x"] // radius), int(p["y"] // radius))].append(i)
    seen: set[int] = set()
    groups = []
    for seed in range(len(points)):
        if seed in seen:
            continue
        seen.add(seed)
        queue = [seed]
        group = []
        while queue:
            i = queue.pop()
            a = points[i]
            group.append(a)
            cell = (int(a["x"] // radius), int(a["y"] // radius))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in buckets.get((cell[0] + dx, cell[1] + dy), []):
                        if j in seen:
                            continue
                        b = points[j]
                        if math.hypot(a["x"] - b["x"], a["y"] - b["y"]) <= radius:
                            seen.add(j)
                            queue.append(j)
        groups.append(group)
    return groups


def hull(points: list[tuple[float, float]]) -> list[list[float]]:
    unique = sorted(set(points))
    if len(unique) >= 3:
        def cross(o, a, b):
            return (a[0]-o[0])*(b[1]-o[1]) - (a[1]-o[1])*(b[0]-o[0])
        lo = []
        for p in unique:
            while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
                lo.pop()
            lo.append(p)
        up = []
        for p in reversed(unique):
            while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
                up.pop()
            up.append(p)
        out = lo[:-1] + up[:-1]
        if len(out) >= 3:
            return [[round(x, 2), round(y, 2)] for x, y in out]
    if len(unique) == 2:
        (x1,y1),(x2,y2)=unique
        dx,dy=x2-x1,y2-y1
        length=math.hypot(dx,dy) or 1
        px,py=-dy/length*22,dx/length*22
        return [[round(x1+px,2),round(y1+py,2)],[round(x2+px,2),round(y2+py,2)],[round(x2-px,2),round(y2-py,2)],[round(x1-px,2),round(y1-py,2)]]
    x,y=unique[0]; r=24
    return [[round(x+math.cos(i*math.pi/4)*r,2),round(y+math.sin(i*math.pi/4)*r,2)] for i in range(8)]


def build(source: Path, data_root: Path, cache: dict[str, dict], site_ids: list[str], catalog: dict[str, dict]) -> tuple[dict, dict]:
    client_rows = read_tsv(source / "client_npcs.tsv")
    client = {r.get("npc_id","").strip(): r for r in client_rows if r.get("npc_id","").strip()}
    roles = {r.get("npc_id","").strip(): r for r in read_tsv(source / "npc_roles.tsv") if r.get("npc_id","").strip()}
    maps = json.loads((data_root / "maps/maps.json").read_text(encoding="utf-8"))
    map_names = {}
    name_path = data_root / "map_names.tsv"
    if name_path.exists():
        for row in read_tsv(name_path):
            map_names[row.get("110010000","")] = row
    else:
        for line in (data_root / "map_names.tsv").read_text(encoding="utf-8-sig").splitlines() if name_path.exists() else []:
            cells=line.split("\t",1)
            if len(cells)==2: map_names[cells[0]]=cells[1]
    mobdata = json.loads(Path("local/bestiary/mobs.json").read_text(encoding="utf-8"))
    points_by_id: dict[str, list[dict]] = defaultdict(list)
    for map_id, points in mobdata.get("zones", {}).items():
        for p in points:
            points_by_id[p["mob_id"]].append({**p, "map_id": map_id})
    services_by_id: dict[str, list[dict]] = defaultdict(list)
    service_path = source / "raw/npc_service_coords.tsv"
    if service_path.exists():
        for r in read_tsv(service_path):
            map_id = ZONE_MAP_IDS.get(r.get("zone","").strip())
            npc_id = r.get("npc_id","").strip()
            if not map_id or not npc_id:
                continue
            tr = maps.get(map_id)
            if not tr:
                continue
            try:
                gx,gy,gz=(float(r[k]) for k in ("x","y","z"))
            except (KeyError,ValueError):
                continue
            ix=tr["x"][0]*gy+tr["x"][1]
            iy=tr["y"][0]*gx+tr["y"][1]
            if 0<=ix<=tr.get("size",3072) and 0<=iy<=tr.get("size",3072):
                services_by_id[npc_id].append({"map_id":map_id,"x":round(ix,2),"y":round(iy,2),"gx":round(gx,2),"gy":round(gy,2),"gz":round(gz,2),"source":"client_world"})
    site_set = set(site_ids)
    all_ids = sorted(site_set | set(client) | set(catalog) | set(cache), key=int)
    records=[]
    for npc_id in all_ids:
        c=client.get(npc_id)
        r=roles.get(npc_id)
        kb=cache.get(npc_id)
        if kb and "error" in kb: kb=None
        cat=catalog.get(npc_id, {})
        details={
            "id":npc_id,
            "name":((kb or {}).get("name","").strip()) or cat.get("name","").strip() or (c or {}).get("russian_name","").strip() or (c or {}).get("internal_name","").strip(),
            "site_name":cat.get("name",""),
            "site_level":(kb or {}).get("level") or cat.get("level"),
            "site_experience":cat.get("experience"),
            "site_hp":cat.get("hp"),
            "internal_name":(c or {}).get("internal_name","").strip(),
            "local_name":(c or {}).get("russian_name","").strip(),
            "function_type":(c or {}).get("function_type","").strip(),
            "ui_type":(c or {}).get("ui_type","").strip(),
            "ai_name":(c or {}).get("ai_name","").strip(),
            "tribe":(c or {}).get("tribe","").strip(),
            "race":(c or {}).get("race_type","").strip(),
            "role":(r or {}).get("function_type","").strip(),
            "category":"npc" if ((c or {}).get("function_type","").strip() or (c or {}).get("race_type","").casefold().startswith("pc_")) else "monster",
            "icon":(kb or {}).get("icon","") or cat.get("icon",""),
            "icon_asset":local_icon((kb or {}).get("icon","") or cat.get("icon","")),
            "site_catalog":cat,
            "kb":kb,
            "points":points_by_id.get(npc_id,[])+services_by_id.get(npc_id,[]),
            "kb_url":f"{BASE}/npc/{npc_id}" if kb or npc_id in site_set or npc_id in catalog else "",
            "kb_status":"loaded" if kb else ("listed_not_fetched" if npc_id in site_ids else "client_only"),
            "seller_inventory":None if ((c or {}).get("function_type","").strip().casefold()=="merchant") else None,
            "seller_inventory_state":"not_published_in_kb_profile",
        }
        records.append(details)
    clusters=[]
    for npc_id, pts in points_by_id.items():
        by_zone=defaultdict(list)
        for p in pts:
            by_zone[p["map_id"]].append(p)
        for map_id, zone_points in by_zone.items():
            for n, group in enumerate(components(zone_points),1):
                center=[round(sum(p[k] for p in group)/len(group),2) for k in ("x","y")]
                clusters.append({
                    "npc_id":npc_id,"map_id":map_id,
                    "area_id":f"{npc_id}:{map_id}:{n}",
                    "point_count":len(group),"center":center,
                    "bounds":[round(min(p["x"] for p in group),2),round(min(p["y"] for p in group),2),round(max(p["x"] for p in group),2),round(max(p["y"] for p in group),2)],
                    "polygon":hull([(p["x"],p["y"]) for p in group]),
                    "area_name":None,
                    "source":"client_spawn_cluster",
                    "precision":"approximate_cluster_not_game_defined_boundary",
                })
    site_area_names: dict[tuple[str, str], set[str]] = defaultdict(set)
    for npc_id, kb in cache.items():
        if "error" in kb:
            continue
        for loc in kb.get("locations", []):
            map_id = SITE_MAP_IDS.get(loc.get("slug", "").casefold())
            if not map_id:
                continue
            for point in loc.get("points", []):
                area = point.get("area") or {}
                name = area.get("name")
                if name:
                    site_area_names[(npc_id, map_id)].add(name)
    for cluster in clusters:
        names = sorted(site_area_names.get((cluster["npc_id"], cluster["map_id"]), set()))
        cluster["area_names"] = names
        cluster["area_name"] = names[0] if len(names) == 1 else None
        cluster["area_source"] = "kb_nearest_subzone" if names else None
    zone_names = {}
    zone_name_file = source.parent / "data/map_names.tsv"
    if zone_name_file.exists():
        for line in zone_name_file.read_text(encoding="utf-8-sig").splitlines():
            cells = line.split("\t", 1)
            if len(cells) == 2:
                zone_names[cells[0]] = cells[1]
    now=datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload={
        "schema_version":1,
        "generated_at":now,
        "sources":{
            "kb":"https://kb.aionempire.com/npcs and /npc/{id}; all catalog, sitemap and client IDs requested; coverage recorded separately; details are server database values",
            "client":"Aion Empire Classic extracted TSV/XML files; client files are read-only references",
            "client_count":len(client),
            "kb_sitemap_count":len(site_ids),
            "kb_catalog_entries":len(catalog),
            "kb_profiles_loaded":sum(1 for x in cache.values() if "error" not in x),
            "kb_profile_failures":sum(1 for x in cache.values() if "error" in x),
            "mob_count":len(mobdata.get("mobs",{})),
            "mob_spawn_points":sum(map(len,mobdata.get("zones",{}).values())),
            "mob_zone_count":len(mobdata.get("zones",{})),
            "service_npc_count":len(services_by_id),
            "seller_inventory":"not present in KB NPC profiles/item pages checked or extracted client NPC/world files",
            "coordinate_note":"client x/y are app map pixels; KB points are preserved in profile locations in KB's own map coordinate system and are not mixed into client pixel coordinates",
            "area_note":"polygons are approximate convex hulls around grouped client spawn points; they are not server-defined territory boundaries",
        },
        "zones":zone_names,
        "records":records,
    }
    return payload, {"schema_version":1,"generated_at":now,"areas":clusters}


def main() -> None:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--client-source",type=Path,required=True)
    ap.add_argument("--data-root",type=Path,default=Path("data"))
    ap.add_argument("--cache",type=Path,default=Path("downloads/aion_kb_bestiary/npc_profiles.jsonl"))
    ap.add_argument("--catalog-cache",type=Path,default=Path("downloads/aion_kb_bestiary/catalog_pages.jsonl"))
    ap.add_argument("--workers",type=int,default=4)
    ap.add_argument("--no-crawl",action="store_true")
    ap.add_argument("--max-profiles",type=int,default=0)
    args=ap.parse_args()
    if args.no_crawl:
        pages = [json.loads(line) for line in args.catalog_cache.read_text(encoding="utf-8").splitlines() if line.strip()]
        catalog = {entry["id"]: entry for page in pages for entry in page.get("entries", [])}
        previous = Path("local/bestiary/npcs.json.gz")
        with gzip.open(previous, "rt", encoding="utf-8") as stream:
            site_ids = [r["id"] for r in json.load(stream)["records"] if r.get("kb_url")]
    else:
        site_ids=sitemap_npc_ids()
        catalog=crawl_catalog(args.catalog_cache,args.workers)
    local=read_tsv(args.client_source/"client_npcs.tsv")
    roles=read_tsv(args.client_source/"npc_roles.tsv")
    service=read_tsv(args.client_source/"raw/npc_service_coords.tsv")
    mobs=json.loads(Path("local/bestiary/mobs.json").read_text(encoding="utf-8"))
    targets=set(site_ids) | set(catalog) | {r.get("id", r.get("npc_id", "")).strip() for r in local}
    targets.update(r.get("npc_id","").strip() for r in roles)
    targets.update(r.get("npc_id","").strip() for r in service)
    site_set=set(site_ids)
    targets={x for x in targets if x and x.isdigit()}
    if not args.no_crawl:
        ids=sorted(targets,key=int)
        if args.max_profiles:
            ids=ids[:args.max_profiles]
        cache=scrape(ids,args.cache,args.workers)
    else:
        cache=load_cache(args.cache)
    payload, areas=build(args.client_source,args.data_root,cache,site_ids,catalog)
    out=Path("local/bestiary/npcs.json.gz")
    out.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(out,"wt",encoding="utf-8",newline="\n",compresslevel=9) as f:
        json.dump(payload,f,ensure_ascii=False,separators=(",",":"))
        f.write("\n")
    area_out=Path("local/bestiary/mob_areas.json.gz")
    with gzip.open(area_out,"wt",encoding="utf-8",newline="\n",compresslevel=9) as f:
        json.dump(areas,f,ensure_ascii=False,separators=(",",":"))
        f.write("\n")
    print(f"Wrote {len(payload['records'])} NPC records, {payload['sources']['kb_profiles_loaded']} KB profiles, "
          f"{len(areas['areas'])} approximate areas; {out.stat().st_size:,} and {area_out.stat().st_size:,} bytes",flush=True)


if __name__=="__main__":
    main()
