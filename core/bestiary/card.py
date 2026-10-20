"""What the NPC card says, from a BestiaryStore.detail() dict: stats, description, places, drops and the merchant stock.

    overview_rows(detail) -> [(name, value)]          level, rank, stats, faction, race
    overview_text(detail) -> str                       title, description and the merchant's trade sections
    place_counts(detail, map_names) -> [(map_id, n)]   spawn points per zone, sorted by zone name
    locations_text(detail) / points_from_text(detail)  the «Локации» block when there are no / borrowed points
    drops_empty_text(detail)                           the «Добыча» block without drops
    filter_drops(detail, query) -> [(index, item)] and drops_note(shown, detail)
    filter_stock(detail, query) -> [(index, item)] and stock_note(shown, total)
    CATEGORY, SORTS, RARITY                            the filter choices and grade names of the tab
Portable core: dicts in, text out.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

CATEGORY = {"Все группы": "", "Монстры": "monster", "NPC": "npc", "Торговцы": "merchant", "Служебные": "service",
            "Низкоуровневые": "low"}
SORTS = {"Сначала с профилем": "", "Уровень ↑": "level_asc", "Уровень ↓": "level_desc",
         "Имя А → Я": "name_asc", "Имя Я → А": "name_desc"}
RARITY = {
    "junk": "Простой", "common": "Обычный", "rare": "Редкий",
    "legend": "Легендарный", "unique": "Уникальный", "epic": "Эпический",
    "mythic": "Мифический",
}
KB_ITEM_URL = "https://kb.aionempire.com/items/{}"


def overview_rows(detail: dict) -> list[tuple[str, object]]:
    stats = detail.get("stats") or {}
    return [("Уровень", detail.get("level") or "Не указан"), ("Ранг", detail.get("rank") or "Не указан"),
            *stats.items(), ("Принадлежность", detail.get("faction") or "Другие"), ("Вид", detail.get("race") or "Не указан")]


def overview_text(detail: dict) -> str:
    text = "\n".join(value for value in (detail.get("title"), detail.get("description")) if value)
    if detail.get("stock"):
        groups = list(dict.fromkeys(item.get("group", "") for item in detail["stock"]))
        text += "\nТорговые разделы: " + ", ".join(filter(None, groups))
    return text.strip()


def place_counts(detail: dict, map_names: Mapping[str, str]) -> list[tuple[str, int]]:
    counts: dict[str, int] = defaultdict(int)
    for point in detail.get("points") or []:
        counts[str(point.get("map_id") or "")] += 1
    return sorted(counts.items(), key=lambda pair: map_names.get(pair[0], pair[0]))


def drops_empty_text(detail: dict) -> str:
    return ("В профиле KB нет списка добычи." if detail.get("kb_status") == "loaded"
            else "Сведения о добыче пока не загружены.")


def locations_text(detail: dict) -> str:
    """The «Локации» block without spawn points: the KB locations, or a note that the client has none."""
    names = [loc.get("name") or loc.get("slug") for loc in detail.get("kb_locations") or []]
    return "По базе KB: " + ", ".join(filter(None, names)) if any(names) else "Точки появления в файлах клиента не найдены."


def points_from_text(detail: dict) -> str:
    return f"Места взяты у одноимённой записи «{detail['points_from']}»." if detail.get("points_from") else ""


def filter_drops(detail: dict, query: str) -> list[tuple[int, dict]]:
    term = query.strip().casefold()
    return [(i, item) for i, item in enumerate(detail.get("drops") or []) if term in str(item.get("name") or "").casefold()]


def drops_note(shown: int, detail: dict) -> str:
    total = len(detail.get("drops") or [])
    if total:
        return f"Показано {shown} из {total}. Шансы выпадения не указаны."
    return "В профиле нет списка добычи." if detail.get("kb_status") == "loaded" else "Сведения о добыче пока не загружены."


def filter_stock(detail: dict, query: str) -> list[tuple[int, dict]]:
    term = query.strip().casefold()
    return [(i, item) for i, item in enumerate(detail.get("stock") or [])
            if term in (item.get("name", "") + " " + item.get("group", "")).casefold()]


def stock_note(shown: int, total: int) -> str:
    if total:
        return f"Показано {shown} из {total}. Ассортимент из клиента; на сервере возможны отличия."
    return "Для этого NPC список товаров в клиенте не найден."
