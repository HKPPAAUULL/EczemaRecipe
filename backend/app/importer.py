"""Seed CSV parsing, validation, synonym merging and DB import.

Pure-Python parts (parse/validate/merge) are psycopg-free so unit tests run
without a database or driver installed. DB work lives in ``import_seed`` /
``run_import`` and is always executed inside one transaction.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

ALLOWED_RATINGS = {"suitable", "caution", "trigger", "unrated"}
RATINGS_REQUIRING_REASON = {"caution", "trigger"}
DEFAULT_ALLERGEN_SEVERITY = "medium"

# allergens column tokens (ingredients_draft.csv) -> allergen.name_zh
ALLERGEN_TOKEN_MAP = {
    "蛋": "蛋",
    "奶": "奶",
    "花生": "花生",
    "堅果": "堅果(樹堅果)",
    "大豆": "大豆",
    "小麥": "小麥",
    "魚": "魚",
    "甲殼類": "甲殼類",
    "芝麻": "芝麻",
    "高組織胺": "組織胺",
    "高水楊酸": "水楊酸",
    "高鎳": "鎳",
    "花粉交叉": "花粉交叉",
}

# repo root = backend/app/importer.py -> parents[2]; absolute so the CLI works
# from any working directory
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = _REPO_ROOT / "data" / "seed" / "ingredients_draft.csv"
DEFAULT_SYNONYMS_CSV = _REPO_ROOT / "data" / "reference" / "ingredient_synonyms.csv"
DEFAULT_SEED_SQL = _REPO_ROOT / "docs" / "db" / "seed_categories_allergens.sql"


class SeedValidationError(ValueError):
    """Raised for any invalid seed row; message always carries the row number."""


@dataclass
class SeedRow:
    row_no: int
    category_zh: str
    name_zh: str
    name_en: str
    aliases: list[str]
    eczema_rating: str
    rating_reason: str
    allergen_tokens: list[str]
    source_urls: list[str]
    needs_senior_review: bool
    notes: str

    @property
    def allergen_names(self) -> list[str]:
        """allergen.name_zh values for this row's tokens (deduped, ordered)."""
        out: list[str] = []
        for token in self.allergen_tokens:
            name = ALLERGEN_TOKEN_MAP[token]
            if name not in out:
                out.append(name)
        return out


def _split(cell: str | None) -> list[str]:
    return [part.strip() for part in (cell or "").split(";") if part.strip()]


def _parse_bool(cell: str | None) -> bool:
    return (cell or "").strip().lower() in {"true", "1", "yes"}


def parse_seed_csv(path: str | Path) -> list[SeedRow]:
    """Parse and validate the seed CSV. Raises SeedValidationError on any issue."""
    rows: list[SeedRow] = []
    seen_names: set[str] = set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"category_zh", "name_zh", "eczema_rating", "allergens"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise SeedValidationError(f"missing CSV columns: {sorted(missing)}")
        for i, raw in enumerate(reader, start=2):  # row 1 = header
            name = (raw["name_zh"] or "").strip()
            rating = (raw["eczema_rating"] or "").strip()
            reason = (raw["rating_reason"] or "").strip()
            if not name:
                raise SeedValidationError(f"row {i}: name_zh is empty")
            if name in seen_names:
                raise SeedValidationError(f"row {i}: duplicate name_zh {name!r}")
            seen_names.add(name)
            if rating not in ALLOWED_RATINGS:
                raise SeedValidationError(
                    f"row {i} ({name}): invalid eczema_rating {rating!r}"
                )
            if rating in RATINGS_REQUIRING_REASON and not reason:
                raise SeedValidationError(
                    f"row {i} ({name}): rating {rating!r} requires rating_reason"
                )
            tokens = _split(raw["allergens"])
            unknown = [t for t in tokens if t not in ALLERGEN_TOKEN_MAP]
            if unknown:
                raise SeedValidationError(
                    f"row {i} ({name}): unknown allergen token(s) {unknown}"
                )
            rows.append(
                SeedRow(
                    row_no=i,
                    category_zh=(raw["category_zh"] or "").strip(),
                    name_zh=name,
                    name_en=(raw["name_en"] or "").strip(),
                    aliases=list(
                        dict.fromkeys(
                            a for a in _split(raw["aliases"]) if a != name
                        )
                    ),
                    eczema_rating=rating,
                    rating_reason=reason,
                    allergen_tokens=tokens,
                    source_urls=_split(raw["source_urls"]),
                    needs_senior_review=_parse_bool(raw["needs_senior_review"]),
                    notes=(raw["notes"] or "").strip(),
                )
            )
    return rows


def validate_categories(rows: list[SeedRow], valid_names: set[str]) -> None:
    """Raise if any row's category_zh is not a known food_category name."""
    for r in rows:
        if r.category_zh not in valid_names:
            raise SeedValidationError(
                f"row {r.row_no} ({r.name_zh}): unknown category {r.category_zh!r}"
            )


def load_seed_category_names(seed_sql_path: str | Path) -> set[str]:
    """Extract food_category names from the INSERT block of the seed SQL file."""
    sql = Path(seed_sql_path).read_text(encoding="utf-8")
    m = re.search(
        r"INSERT\s+INTO\s+food_category\s*\([^)]*\)\s*VALUES(.*?);",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        raise SeedValidationError(
            f"cannot find food_category INSERT in {seed_sql_path}"
        )
    return set(re.findall(r"\(\s*'([^']+)'\s*,", m.group(1)))


def load_synonym_groups(path: str | Path) -> dict[str, list[str]]:
    """canonical_zh -> ordered, deduped alias list."""
    groups: dict[str, list[str]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            canon = (r["canonical_zh"] or "").strip()
            alias = (r["alias"] or "").strip()
            if not canon or not alias:
                continue
            bucket = groups.setdefault(canon, [])
            if alias not in bucket:
                bucket.append(alias)
    return groups


def merge_synonym_aliases(
    rows: list[SeedRow], groups: dict[str, list[str]]
) -> int:
    """Merge synonym-group aliases into matching seed rows (in place).

    A group matches a row when its canonical_zh equals the row's name_zh or one
    of its aliases. The canonical itself is added too. Iterates to a fixpoint so
    newly added aliases can match further groups. Returns the number of
    canonicals that matched no row.
    """
    matched: set[str] = set()
    changed = True
    while changed:
        changed = False
        for row in rows:
            keys = {row.name_zh, *row.aliases}
            for canon, aliases in groups.items():
                if canon not in keys:
                    continue
                matched.add(canon)
                for alias in [canon, *aliases]:
                    if alias != row.name_zh and alias not in row.aliases:
                        row.aliases.append(alias)
                        changed = True
    return len(groups) - len(matched)


@dataclass
class ImportSummary:
    rows_total: int = 0
    inserted: int = 0
    updated: int = 0
    rating_counts: dict[str, int] = field(default_factory=dict)
    needs_senior_review: int = 0
    allergen_links: int = 0
    evidence_inserted: int = 0
    data_sources_created: int = 0
    synonym_canonicals_unmatched: int = 0

    def format(self, dry_run: bool = False) -> str:
        lines = [
            f"import-seed summary{' (dry-run: rolled back)' if dry_run else ''}:",
            f"  rows: {self.rows_total} (inserted={self.inserted}, updated={self.updated})",
            "  ratings: "
            + ", ".join(
                f"{k}={v}" for k, v in sorted(self.rating_counts.items())
            ),
            f"  needs_senior_review: {self.needs_senior_review}",
            f"  allergen links written: {self.allergen_links}",
            f"  evidence rows inserted: {self.evidence_inserted}",
            f"  data sources created: {self.data_sources_created}",
            f"  synonym canonicals unmatched: {self.synonym_canonicals_unmatched}",
        ]
        return "\n".join(lines)


def _source_title(url: str) -> str:
    parsed = urlparse(url.strip())
    title = (parsed.netloc + parsed.path).rstrip("/")
    return title[:200] or "draft source"


def _ensure_data_source(conn, url: str, summary: ImportSummary) -> int:
    """Return data_source.id for the URL's domain, creating it (kind='web')."""
    parsed = urlparse(url.strip())
    domain = parsed.netloc or "unknown"
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else None
    row = conn.execute(
        "SELECT id FROM data_source WHERE name = %s", (domain,)
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        """INSERT INTO data_source (name, url, license, kind)
           VALUES (%s, %s, NULL, 'web') RETURNING id""",
        (domain, origin),
    ).fetchone()
    summary.data_sources_created += 1
    return row[0]


def import_seed(conn, rows: list[SeedRow], unmatched_canonicals: int = 0) -> ImportSummary:
    """Upsert all seed rows into the DB.

    Must be called inside a transaction owned by the caller (``run_import``
    provides one). ``ingredient.reviewed`` is never written: inserts rely on
    the column DEFAULT false and updates never touch it.
    """
    categories = {
        name: cid
        for cid, name in conn.execute("SELECT id, name_zh FROM food_category")
    }
    validate_categories(rows, set(categories))

    allergen_ids = {
        name: aid
        for aid, name in conn.execute("SELECT id, name_zh FROM allergen")
    }
    needed = {name for r in rows for name in r.allergen_names}
    missing = needed - set(allergen_ids)
    if missing:
        raise SeedValidationError(
            f"allergen rows missing from allergen table: {sorted(missing)}"
        )

    summary = ImportSummary(
        rows_total=len(rows), synonym_canonicals_unmatched=unmatched_canonicals
    )
    for r in rows:
        existing = conn.execute(
            "SELECT id FROM ingredient WHERE name_zh = %s", (r.name_zh,)
        ).fetchone()
        if existing:
            iid = existing[0]
            conn.execute(
                """UPDATE ingredient SET
                       name_en = %s, aliases = %s, category_id = %s,
                       eczema_rating = %s, rating_reason = %s,
                       needs_senior_review = %s
                   WHERE id = %s""",
                (
                    r.name_en or None,
                    r.aliases,
                    categories[r.category_zh],
                    r.eczema_rating,
                    r.rating_reason or None,
                    r.needs_senior_review,
                    iid,
                ),
            )
            summary.updated += 1
        else:
            iid = conn.execute(
                """INSERT INTO ingredient
                       (name_zh, name_en, aliases, category_id, eczema_rating,
                        rating_reason, needs_senior_review)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    r.name_zh,
                    r.name_en or None,
                    r.aliases,
                    categories[r.category_zh],
                    r.eczema_rating,
                    r.rating_reason or None,
                    r.needs_senior_review,
                ),
            ).fetchone()[0]
            summary.inserted += 1

        conn.execute(
            "DELETE FROM ingredient_allergen WHERE ingredient_id = %s", (iid,)
        )
        for aname in r.allergen_names:
            conn.execute(
                """INSERT INTO ingredient_allergen
                       (ingredient_id, allergen_id, severity)
                   VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
                (iid, allergen_ids[aname], DEFAULT_ALLERGEN_SEVERITY),
            )
            summary.allergen_links += 1

        for url in r.source_urls:
            _ensure_data_source(conn, url, summary)
            cur = conn.execute(
                """INSERT INTO evidence
                       (ingredient_id, title, url, summary, source_type, year)
                   VALUES (%s, %s, %s, NULL, 'other', NULL)
                   ON CONFLICT (ingredient_id, url) DO NOTHING""",
                (iid, _source_title(url), url),
            )
            if cur.rowcount:
                summary.evidence_inserted += 1

        summary.rating_counts[r.eczema_rating] = (
            summary.rating_counts.get(r.eczema_rating, 0) + 1
        )
        summary.needs_senior_review += int(r.needs_senior_review)
    return summary


def run_import(
    database_url: str,
    rows: list[SeedRow],
    unmatched_canonicals: int = 0,
    dry_run: bool = False,
) -> ImportSummary:
    """Execute the import in ONE transaction; dry-run rolls back at the end."""
    import psycopg  # lazy: unit tests run without the driver installed

    with psycopg.connect(database_url) as conn:
        try:
            summary = import_seed(conn, rows, unmatched_canonicals)
            if dry_run:
                conn.rollback()
            else:
                conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return summary
