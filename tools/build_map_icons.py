"""Make the map layer icons (data/maps/icons/*.png) from ready-made sources only.

Sources (nothing is drawn here):
  * the client's own map icons — client_extract/icons/*.png (extracted by Codex);
  * the client's own UI sprites — a sprite name from the client's sprite tables
    (client_extract/raw/Data/ui/preload/preload/*.txt.xml: name, src_image="x,y,w,h", texture) cut from
    client_extract/raw/textures/ui/ui/<texture>.png, e.g. the NPC dialog function icons v5_npc_func_*;
  * aiondb.ru map icons — downloads/aiondb_icons/aiondb_map_icons.json: the site's
    <pattern id="map_icon_..."> markup (vector icons) and links to its PNG icons.
Vector icons are rasterised with the local Chrome in headless mode.
Dev tool (needs Pillow and Chrome). Usage: python tools/build_map_icons.py [type ...]  (default: all)
"""

import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRACT = ROOT / "client_extract"
OUT = ROOT / "client_extract" / "icons_native"  # native size; tools/upscale_icons.py --install puts the x4 ones in data/maps/icons
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
SIZE = 48  # px, square canvas; the app scales down
AIONDB = "https://aiondb.ru"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120", "Referer": "https://aiondb.ru/maps/"}

# layer type -> source: ("sprite", client sprite name[@texture]), ("client", file) or ("aiondb", pattern id).
# NPCs use the icons the game's own map and radar draw (v4_radar_*, checked on an in-game screenshot).
ICONS = {
    "teleport": ("sprite", "v4_radar_icon_teleport"),
    "warehouse": ("sprite", "v4_radar_icon_warehouse"),
    "merchant": ("sprite", "v4_radar_icon_merchant"),
    "coin_merchant": ("sprite", "coin_merchant_marker@v4_common"),
    "vendor": ("sprite", "v4_radar_icon_vendor"),
    "stigma": ("sprite", "v4_radar_icon_stigma_master"),
    "postbox": ("sprite", "v4_radar_postbox_icon"),
    "bindstone": ("sprite", "v4_radar_bindstone_icon"),
    "quest_point": ("sprite", "v4_radar_quest_icon_zonemap"),
    # NPCs with a quest to give, as the game's map marks them
    "quest_give": ("sprite", "v4_radar_quest_give_icon_zonemap"),
    "quest_important": ("sprite", "v4_radar_important_quest_give_icon_zonemap"),
    "quest_event": ("sprite", "v4_radar_event_quest_give_icon_zonemap"),
    "artifact": ("client", "abyss_artifact.png"),
    "fortress": ("client", "abyss_fortress.png"),
    "dungeon": ("client", "abyss_indun.png"),
    "raid_boss": ("client", "abyss_bossraid_dark.png"),
    "tunnel": ("client", "abyss_underpass.png"),
    "portal": ("client", "abyss_underpass.png"),
    "direct_portal": ("client", "teleport_dest_up.png"),
    "camp": ("aiondb", "map_icon_ui_camp"),
    # gathering: the game's item icons that aiondb uses for its gathering filters
    "gather_herb": ("aiondb_url", "/upload/images/icon/items/icon_item_herb01.png"),
    "gather_aether": ("aiondb_url", "/upload/images/icon/items/icon_item_od04.png"),
    "gather_berry": ("aiondb_url", "/upload/images/icon/items/icon_item_fruit07.png"),
    "gather_vegetable": ("aiondb_url", "/upload/images/icon/items/icon_item_vegetable03.png"),
    "gather_tree": ("aiondb_url", "/upload/images/icon/items/icon_item_log01a.png"),
    "gather_noblemetal": ("aiondb_url", "/upload/images/icon/items/icon_item_rock01b.png"),
    "gather_plant": ("aiondb_url", "/upload/images/icon/items/icon_item_jute01c.png"),
    "gather_metal": ("aiondb_url", "/upload/images/icon/items/icon_item_rock01c.png"),
    "gather_shell": ("aiondb_url", "/upload/images/icon/items/icon_item_seefood02.png"),
    "gather_jewelry": ("aiondb_url", "/upload/images/icon/items/icon_item_gemstone02c.png"),
    "gather_fish": ("aiondb_url", "/upload/images/icon/items/icon_item_fish04.png"),
    "gather_other": ("client", "new_map_way_point.png"),
}


def pattern_to_svg(pattern: str) -> str:
    """<pattern … viewBox=…>…</pattern> -> a standalone square <svg>."""
    view_box = re.search(r'viewBox="([^"]+)"', pattern).group(1)
    inner = re.sub(r"^<pattern[^>]*>", "", pattern)
    inner = re.sub(r"</pattern>$", "", inner)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{SIZE}" height="{SIZE}" viewBox="{view_box}" preserveAspectRatio="xMidYMid meet">{inner}</svg>'
    )


def render_svg(svg: str, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "icon.html"
        page.write_text(
            f'<html><body style="margin:0;background:transparent">{svg}</body></html>', encoding="utf-8"
        )
        shot = Path(tmp) / "shot.png"
        subprocess.run(
            [str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--window-size={SIZE},{SIZE}", "--default-background-color=00000000",
             f"--screenshot={shot}", page.as_uri()],
            check=True, capture_output=True, timeout=60,
        )
        from PIL import Image

        with Image.open(shot) as image:
            image.convert("RGBA").crop((0, 0, SIZE, SIZE)).save(out)


def fetch_png(pattern: str, out: Path) -> None:
    href = re.search(r'href="([^"]+\.png)"', pattern).group(1)
    with urllib.request.urlopen(urllib.request.Request(AIONDB + href, headers=HEADERS), timeout=30) as r:
        out.write_bytes(r.read())


SPRITE_RE = re.compile(r'name="([^"]+)" src_image="(\d+),(\d+),(\d+),(\d+)" texture="([^"]+)"')


def sprite_table(texts: list[str]) -> dict[str, list[tuple[str, tuple[int, int, int, int]]]]:
    """Client sprite tables -> {sprite name: [(texture file stem in lower case, (x, y, w, h)), ...]}."""
    out: dict[str, list[tuple[str, tuple[int, int, int, int]]]] = {}
    for text in texts:
        for name, x, y, w, h, texture in SPRITE_RE.findall(text):
            entry = (texture.replace("\\", "/").rsplit("/", 1)[-1].lower(), (int(x), int(y), int(w), int(h)))
            if entry not in out.setdefault(name, []):
                out[name].append(entry)
    return out


def cut_sprite(key: str, table: dict, out: Path) -> None:
    """key = sprite name, or «name@texture» when the name exists in several atlases."""
    from PIL import Image

    name, _at, wanted = key.partition("@")
    texture, (x, y, w, h) = next(e for e in table[name] if not wanted or e[0] == wanted.lower())
    folder = EXTRACT / "raw" / "textures" / "ui" / "ui"
    path = next(p for p in folder.glob("*.png") if p.stem.lower() == texture)
    with Image.open(path) as atlas:
        atlas.convert("RGBA").crop((x, y, x + w, y + h)).save(out)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    patterns = json.loads((ROOT / "downloads" / "aiondb_icons" / "aiondb_map_icons.json").read_text(encoding="utf-8"))
    tables = sorted((EXTRACT / "raw" / "Data" / "ui" / "preload" / "preload").glob("*.txt.xml"))
    sprites = sprite_table([t.read_text(encoding="utf-8") for t in tables])
    wanted = set(sys.argv[1:])
    for type_, (source, key) in ICONS.items():
        if wanted and type_ not in wanted:
            continue
        out = OUT / f"{type_}.png"
        if source == "sprite":
            cut_sprite(key, sprites, out)
        elif source == "client":
            out.write_bytes((EXTRACT / "icons" / key).read_bytes())
        elif source == "aiondb_url":
            fetch_png(f'href="{key}"', out)
        elif "<image" in patterns[key]:
            fetch_png(patterns[key], out)
        else:
            render_svg(pattern_to_svg(patterns[key]), out)
        print(f"{type_:15s} <- {source}:{key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
