"""Reading the exported tables: tab separated text with a header line, UTF-8 (a BOM is fine).

An empty cell is ``None``: «unknown», not an empty string. A missing file is an empty table, so a section whose
source is not there yet is built empty and named in the report.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path


def read_tsv(path: Path | None, delimiter: str = "\t") -> list[dict[str, str | None]]:
    """Rows as dicts by the header; ``None`` for an empty cell; ``[]`` when the file is not there.
    (``delimiter=","`` reads the one comma separated file, data/watch_items.csv.)"""
    if path is None or not Path(path).is_file():
        return []
    with open(path, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        return [{key: (value if value != "" else None) for key, value in row.items() if key is not None} for row in reader]


def iter_tsv(path: Path | None) -> Iterator[dict[str, str | None]]:
    """The same rows one by one, for tables too big to hold in memory (the drops: 1.4 million rows)."""
    if path is None or not Path(path).is_file():
        return
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            yield {key: (value if value != "" else None) for key, value in row.items() if key is not None}


def read_pairs(path: Path | None) -> dict[str, str]:
    """A file without a header, ``id<TAB>text`` per line (the old data/item_names.tsv); the last line of an id wins."""
    pairs: dict[str, str] = {}
    if path is None or not Path(path).is_file():
        return pairs
    with open(path, encoding="utf-8-sig", newline="") as handle:
        for line in handle:
            key, _, value = line.rstrip("\r\n").partition("\t")
            if key.isdigit() and value:
                pairs[key] = value
    return pairs


def to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        try:
            number = float(value)
        except ValueError:
            return None
        return int(number) if number == int(number) else None


def to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
