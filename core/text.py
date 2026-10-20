"""Small Russian text helpers shared by the core groups."""


def plural(n: int, one: str, few: str, many: str) -> str:
    """«1 слово», «3 слова», «5 слов» (Russian plural forms)."""
    last2, last = n % 100, n % 10
    word = one if last == 1 and last2 != 11 else few if 2 <= last <= 4 and not 12 <= last2 <= 14 else many
    return f"{n} {word}"


def split_keywords(text: str) -> list[str]:
    """«хил, ММК ,,чант» -> ["хил", "ММК", "чант"]."""
    return [part.strip() for part in text.split(",") if part.strip()]


def metres_text(metres: float) -> str:
    """«384 м», «1.6 км»."""
    return f"{round(metres)} м" if metres < 1000 else f"{metres / 1000:.1f} км"
