"""Write crawled recipes to the DB in ONE transaction (idempotent).

- status is always pending_review on insert; a recipe whose status was
  manually set to published/rejected is never overwritten on re-import.
- recipe_ingredient stores matched items only (merged per ingredient_id,
  raw_text joined with 「；」); unmatched raw texts go to
  recipe.unmatched_ingredients; allergen_hints scans ALL raw items.
- published_recipe view additionally requires cardinality(unmatched)=0.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from app.crawler.allergens import load_keyword_map, scan_allergens
from app.crawler.matcher import IngredientMatcher
from app.crawler.parse import normalize

_REPO = Path(__file__).resolve().parents[3]
STAPLE_CSV = _REPO / "data" / "reference" / "staple_ingredients.csv"
ALLERGEN_CSV = _REPO / "data" / "reference" / "allergen_keywords.csv"
REPORT_MD = _REPO / "data" / "reference" / "recipe_match_report_hakka.md"


def load_staples(path: str | Path = STAPLE_CSV) -> set[str]:
    from app.crawler.parse import normalize

    out: set[str] = set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["name"].strip():
                out.add(normalize(r["name"]))
    return out


@dataclass
class CrawlStats:
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    skipped_manual_status: int = 0
    parse_failed: int = 0
    matched_items: int = 0
    unmatched_items: int = 0
    unmatched_staples: int = 0
    recipes_fully_matched: int = 0
    match_rate: float = 0.0
    top_unmatched: list[tuple[str, int]] = field(default_factory=list)

    def as_json(self) -> dict:
        return {
            "fetched": self.fetched,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped_unchanged": self.skipped_unchanged,
            "skipped_manual_status": self.skipped_manual_status,
            "parse_failed": self.parse_failed,
            "matched_items": self.matched_items,
            "unmatched_items": self.unmatched_items,
            "unmatched_staples": self.unmatched_staples,
            "match_rate": round(self.match_rate, 4),
        }


def _ensure_source(conn, name: str, url: str, license_: str) -> int:
    row = conn.execute(
        "SELECT id FROM data_source WHERE name = %s", (name,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE data_source SET url=%s, license=%s, kind='recipe' "
            "WHERE id=%s",
            (url, license_, row[0]),
        )
        return row[0]
    return conn.execute(
        "INSERT INTO data_source (name,url,license,kind) "
        "VALUES (%s,%s,%s,'recipe') RETURNING id",
        (name, url, license_),
    ).fetchone()[0]


def import_recipes(conn, source_name, source_url, license_, records,
                   keyword_map=None, staples=None) -> CrawlStats:
    keyword_map = keyword_map or load_keyword_map(ALLERGEN_CSV)
    staples = staples if staples is not None else load_staples()
    matcher = IngredientMatcher.from_rows(
        conn.execute("SELECT id, name_zh, aliases FROM ingredient")
    )
    ds_id = _ensure_source(conn, source_name, source_url, license_)
    stats = CrawlStats(fetched=len(records))
    unmatched_names: dict[str, int] = {}

    for rec in records:
        if rec.parse_failed:
            stats.parse_failed += 1
        matched: dict[int, list] = {}
        unmatched: list[str] = []
        unmatched_staple: list[str] = []
        all_items = [*rec.items, *rec.seasoning_items]
        for it in all_items:
            iid = matcher.match(it.name)
            if iid is None:
                # staple condiments go to unmatched_staples: they do not
                # block publication, but allergen_hints below still scans
                # their raw text (醬油/蠔油/麵粉/芝麻油 risks are keyword-hit)
                if normalize(it.name) in staples:
                    unmatched_staple.append(it.raw_text)
                else:
                    unmatched.append(it.raw_text)
                    unmatched_names[it.name] = (
                        unmatched_names.get(it.name, 0) + 1)
            else:
                matched.setdefault(iid, []).append(it)
        stats.matched_items += sum(len(v) for v in matched.values())
        stats.unmatched_items += len(unmatched)
        stats.unmatched_staples += len(unmatched_staple)
        if not unmatched and not rec.parse_failed:
            stats.recipes_fully_matched += 1
        hints = scan_allergens([i.raw_text for i in all_items], keyword_map)

        row = conn.execute(
            "SELECT id, status, content_hash FROM recipe WHERE source_url=%s",
            (rec.source_url,),
        ).fetchone()
        if row and row[2] == rec.content_hash:
            stats.skipped_unchanged += 1
            continue
        if row and row[1] in ("published", "rejected"):
            stats.skipped_manual_status += 1
            continue
        if row:
            rid = row[0]
            conn.execute(
                "UPDATE recipe SET title=%s, description=%s, data_source_id=%s,"
                " content_hash=%s, unmatched_ingredients=%s,"
                " unmatched_staples=%s, allergen_hints=%s"
                " WHERE id=%s",
                (rec.title, rec.description or None, ds_id, rec.content_hash,
                 unmatched, unmatched_staple, hints, rid),
            )
            conn.execute(
                "DELETE FROM recipe_ingredient WHERE recipe_id=%s", (rid,))
            conn.execute("DELETE FROM recipe_tag WHERE recipe_id=%s", (rid,))
            stats.updated += 1
        else:
            rid = conn.execute(
                "INSERT INTO recipe (title, description, source_url,"
                " data_source_id, status, content_hash, unmatched_ingredients,"
                " unmatched_staples, allergen_hints)"
                " VALUES (%s,%s,%s,%s,'pending_review',%s,%s,%s,%s)"
                " RETURNING id",
                (rec.title, rec.description or None, rec.source_url, ds_id,
                 rec.content_hash, unmatched, unmatched_staple, hints),
            ).fetchone()[0]
            stats.inserted += 1
            conn.execute(
                "INSERT INTO review_queue (entity_type, entity_id, status,"
                " reviewer_note) VALUES ('recipe', %s, 'pending', %s)",
                (rid, (f"unmatched={len(unmatched)};"
                       f"unmatched_staples={len(unmatched_staple)};"
                       f"allergen_hints="
                       f"{','.join(hints) if hints else 'none'}")),
            )

        for iid, its in matched.items():
            qty = next((i.qty for i in its if i.qty is not None), None)
            unit = next((i.unit for i in its if i.unit), None)
            conn.execute(
                "INSERT INTO recipe_ingredient (recipe_id, ingredient_id,"
                " raw_text, qty, unit, is_staple) VALUES (%s,%s,%s,%s,%s,%s)"
                " ON CONFLICT (recipe_id, ingredient_id) DO UPDATE SET"
                " raw_text=EXCLUDED.raw_text, qty=EXCLUDED.qty,"
                " unit=EXCLUDED.unit, is_staple=EXCLUDED.is_staple",
                (rid, iid, "；".join(i.raw_text for i in its), qty, unit,
                 any(normalize(i.name) in staples for i in its)),
            )
        for tag in rec.tags:
            conn.execute(
                "INSERT INTO recipe_tag (recipe_id, tag) VALUES (%s,%s)"
                " ON CONFLICT DO NOTHING", (rid, tag))

    total = stats.matched_items + stats.unmatched_items
    stats.match_rate = stats.matched_items / total if total else 0.0
    stats.top_unmatched = sorted(
        unmatched_names.items(), key=lambda kv: (-kv[1], kv[0]))[:50]
    return stats


def write_report(records, stats: CrawlStats, path: str | Path = REPORT_MD) -> None:
    failed = [r.title for r in records if r.parse_failed]
    lines = [
        "# 客家食譜配對報告（crawl-recipes --source hakka）", "",
        f"- 食譜總數：{stats.fetched}",
        (f"- 配對項目：{stats.matched_items}；"
         f"未配對項目：{stats.unmatched_items}（分母只算非 staple 項目）"),
        f"- staple 未配對：{stats.unmatched_staples} 項",
        f"- 配對率：{stats.match_rate:.1%}",
        f"- 完全配對食譜：{stats.recipes_fully_matched}",
        f"- 解析失敗：{stats.parse_failed}", "",
        "## 最常見未配對食材 Top 50", "",
        "| 食材原文 | 次數 |", "|---|---|",
    ]
    lines += [f"| {n} | {c} |" for n, c in stats.top_unmatched]
    lines += ["", "## 解析失敗清單", ""]
    lines += [f"- {t}" for t in failed] if failed else ["（無）"]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def run_import(database_url: str, source_name: str, source_url: str,
               license_: str, records, dry_run: bool = False) -> CrawlStats:
    import psycopg  # lazy: unit tests run without the driver

    stats: CrawlStats | None = None
    with psycopg.connect(database_url, autocommit=True) as conn:
        job_id = conn.execute(
            "INSERT INTO crawl_job (source, status) VALUES (%s, 'running')"
            " RETURNING id", (source_name,)).fetchone()[0]
    try:
        with psycopg.connect(database_url) as conn:
            try:
                stats = import_recipes(
                    conn, source_name, source_url, license_, records)
                status = "cancelled" if dry_run else "succeeded"
                conn.execute(
                    "UPDATE crawl_job SET status=%s, finished_at=now(),"
                    " stats=%s WHERE id=%s",
                    (status, json.dumps(stats.as_json()), job_id))
                if dry_run:
                    conn.rollback()
                else:
                    conn.commit()
            except BaseException:
                conn.rollback()
                raise
    except BaseException as exc:
        with psycopg.connect(database_url, autocommit=True) as conn:
            conn.execute(
                "UPDATE crawl_job SET status='failed', finished_at=now(),"
                " error=%s WHERE id=%s", (str(exc)[:500], job_id))
        raise
    return stats
