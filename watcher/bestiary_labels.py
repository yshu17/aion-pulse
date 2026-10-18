"""Stable, localized bestiary categories shared by indexing and presentation."""

import re


def stat_text(value: object) -> str:
    """Group large numeric values without changing labels or rank numbers."""
    return re.sub(r"\d{4,}", lambda match: f"{int(match.group()):,}".replace(",", " "), str(value))

FACTIONS = ("Элийцы", "Асмодиане", "Балауры", "Другие")

RACES = {
    "pc_light": "Элиец", "pc_dark": "Асмодианин", "drakan": "Балаур",
    "dragon": "Балаур", "naga": "Нага", "beast": "Зверь",
    "demihumanoid": "Полугуманоид", "humanoid": "Гуманоид", "undead": "Нежить",
    "magicalmonster": "Магическое существо", "lizardman": "Ящер",
    "brownie": "Брауни", "construct": "Конструкт", "shulack": "Шурак",
    "krall": "Кралл", "elemental": "Элементаль", "lycan": "Ликан",
    "ratman": "Ратман", "goblin": "Гоблин", "npc": "NPC",
    "teleporter": "Привратник", "barrier": "Барьер", "carrier": "Перевозчик",
    "outsider": "Иное существо", "livingwater": "Живая вода", "neut": "Нейтральный",
    "aggressivesinglemonster": "Монстр",
}


def faction_for(raw_race: str, display_race: str = "") -> str:
    """Group client codes case-insensitively; do not infer allegiance from a name."""
    value = raw_race.strip().casefold()
    display = display_race.strip().casefold()
    if value.startswith(("pc_light", "gchief_light", "ghenchman_light")) or display in ("элиец", "элийцы", "elyos"):
        return "Элийцы"
    if value.startswith(("pc_dark", "gchief_dark", "ghenchman_dark")) or display in ("асмодианин", "асмодиане", "asmodian"):
        return "Асмодиане"
    if value in ("drakan", "dragon", "naga") or value.startswith("dragon_castle") or display in ("балаур", "балауры", "balaur"):
        return "Балауры"
    return "Другие"


def race_label(raw_race: str, display_race: str = "") -> str:
    if display_race and any("а" <= c.casefold() <= "я" for c in display_race):
        return display_race.strip()
    value = (display_race or raw_race).strip().casefold()
    if value in RACES:
        return RACES[value]
    group = faction_for(raw_race, display_race)
    return group if group != "Другие" else "Другое существо"
