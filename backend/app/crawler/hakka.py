"""Hakka dataset adapter: JSON → RecipeRecord list (title/desc/tags/items).

Source: 客委會「客家創意菜色及經典菜餚食譜(歷史資料)」,
https://data.gov.tw/dataset/147690 — 政府資料開放授權條款-第1版（顯名）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.crawler.base import content_hash, fetch_bytes, stable_recipe_slug
from app.crawler.parse import ParsedItem, parse_practic

SOURCE_NAME = "客委會客家創意菜色及經典菜餚食譜"
SOURCE_URL = "https://data.gov.tw/dataset/147690"
SOURCE_LICENSE = "政府資料開放授權條款-第1版"
JSON_URL = "https://cloud.hakka.gov.tw/Pub/Opendata/DTST20220100004.json"
DEFAULT_RAW = (
    Path(__file__).resolve().parents[3] / "data" / "raw" / "hakka_recipes.json"
)


@dataclass
class RecipeRecord:
    title: str
    description: str
    source_url: str
    tags: list[str]
    content_hash: str
    items: list[ParsedItem] = field(default_factory=list)
    seasoning_items: list[ParsedItem] = field(default_factory=list)
    parse_failed: bool = False


def download_raw(dest: Path = DEFAULT_RAW, url: str = JSON_URL) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(fetch_bytes(url))
    return dest


def _clean(s: str | None) -> str:
    return (s or "").strip()


def load_records(path: str | Path, limit: int | None = None) -> list[RecipeRecord]:
    raw = Path(path).read_text(encoding="utf-8-sig")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise TypeError("hakka raw JSON is not a list")
    records: list[RecipeRecord] = []
    for row in data[:limit] if limit else data:
        title = _clean(row.get("dishes_name"))
        if not title:
            continue
        parsed = parse_practic(row.get("practic") or "")
        desc = "；".join(
            p for p in (_clean(row.get("kind")), _clean(row.get("classification")),
                        _clean(row.get("specialty_dishes"))) if p and p != "-"
        )
        tags = [t for t in (_clean(row.get("kind")),
                            _clean(row.get("classification"))) if t and t != "-"]
        items = parsed.items if parsed else []
        rec = RecipeRecord(
            title=title,
            description=desc,
            source_url=f"{SOURCE_URL}#{stable_recipe_slug(title)}",
            tags=tags,
            content_hash=content_hash(
                title, desc,
                *[i.raw_text for i in items], *tags,
            ),
            items=parsed.materials if parsed else [],
            seasoning_items=parsed.seasonings if parsed else [],
            parse_failed=parsed is None,
        )
        records.append(rec)
    return records
