"""Allergen keyword scan over raw item text (safety-critical).

Keyword list comes exclusively from data/reference/allergen_keywords.csv —
hidden forms included; never invent keywords here.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.crawler.parse import normalize


def load_keyword_map(path: str | Path) -> dict[str, str]:
    """normalized keyword -> allergen name_zh."""
    out: dict[str, str] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            kw = normalize(r["keyword"])
            if kw:
                out[kw] = r["allergen"].strip()
    return out


def scan_allergens(texts: list[str], keyword_map: dict[str, str]) -> list[str]:
    """Allergen names hit by any keyword contained in any text (sorted)."""
    hits: set[str] = set()
    for t in texts:
        norm = normalize(t)
        if not norm:
            continue
        for kw, name in keyword_map.items():
            if kw and kw in norm:
                hits.add(name)
    return sorted(hits)
