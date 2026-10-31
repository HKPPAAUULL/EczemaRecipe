"""傳統說法（中醫觀點）種子匯入：data/seed/tradition_notes.csv → ingredient_tradition_note。

內容屬「非實證」資料（DESIGN_REVIEW §4）：一律 reviewed=false 匯入，等人工在
/admin 逐條審核；重跑冪等，且永不改動已審核狀態。

驗證：表頭須完全一致；tag 限白名單；note 不可空且不得含療效／絕對用語
（沿用 admin.rules.find_forbidden_terms）；source_title 不可空；
source_url 須 https://。
配對：ingredient_zh 只與 ingredient.name_zh 精確比對（不做別名／模糊猜測）；
找不到的食材名列出並略過，不視為錯誤。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from app.admin.rules import find_forbidden_terms

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRADITION_CSV = REPO_ROOT / "data" / "seed" / "tradition_notes.csv"

EXPECTED_HEADER = ["ingredient_zh", "tag", "note", "source_title", "source_url"]
ALLOWED_TAGS = {"fawu", "sticky", "warm_hot", "cool", "neutral", "other"}


class TraditionValidationError(ValueError):
    """Raised for invalid tradition-notes data; message carries the row number."""


@dataclass
class TraditionRow:
    row_no: int
    ingredient_zh: str
    tag: str
    note: str
    source_title: str
    source_url: str


def parse_tradition_csv(path: str | Path) -> list[TraditionRow]:
    """Parse and validate the tradition-notes CSV."""
    rows: list[TraditionRow] = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if list(reader.fieldnames or []) != EXPECTED_HEADER:
            raise TraditionValidationError(
                f"header must be exactly {EXPECTED_HEADER}, "
                f"got {list(reader.fieldnames or [])}"
            )
        for i, raw in enumerate(reader, start=2):  # row 1 = header
            name = (raw["ingredient_zh"] or "").strip()
            tag = (raw["tag"] or "").strip()
            note = (raw["note"] or "").strip()
            title = (raw["source_title"] or "").strip()
            url = (raw["source_url"] or "").strip()
            if not name:
                raise TraditionValidationError(f"row {i}: ingredient_zh is empty")
            if tag not in ALLOWED_TAGS:
                raise TraditionValidationError(
                    f"row {i} ({name}): invalid tag {tag!r} "
                    f"(allowed: {sorted(ALLOWED_TAGS)})"
                )
            if not note:
                raise TraditionValidationError(f"row {i} ({name}): note is empty")
            bad = find_forbidden_terms(note)
            if bad:
                raise TraditionValidationError(
                    f"row {i} ({name}): note contains forbidden claim term(s) "
                    f"{bad}"
                )
            if not title:
                raise TraditionValidationError(
                    f"row {i} ({name}): source_title is empty"
                )
            if not url.startswith("https://"):
                raise TraditionValidationError(
                    f"row {i} ({name}): source_url must start with https://"
                )
            rows.append(
                TraditionRow(
                    row_no=i, ingredient_zh=name, tag=tag, note=note,
                    source_title=title, source_url=url,
                )
            )
    if not rows:
        raise TraditionValidationError("tradition CSV has no data rows")
    return rows


@dataclass
class TraditionImportSummary:
    rows_total: int = 0
    inserted: int = 0
    updated: int = 0
    unmatched_names: list[str] = field(default_factory=list)

    def format(self, dry_run: bool = False) -> str:
        lines = [
            (
                "import-tradition summary"
                f"{' (dry-run: rolled back)' if dry_run else ''}:"
            ),
            (
                f"  rows: {self.rows_total} "
                f"(inserted={self.inserted}, updated={self.updated})"
            ),
            f"  unmatched ingredients (skipped): {len(self.unmatched_names)}",
        ]
        if self.unmatched_names:
            lines.append(
                "  unmatched names: " + "、".join(self.unmatched_names)
            )
        return "\n".join(lines)


def import_tradition(conn, rows: list[TraditionRow]) -> TraditionImportSummary:
    """Upsert tradition notes. Caller owns the transaction (``run_import``).

    ``reviewed`` is never written: inserts rely on the column DEFAULT false and
    ON CONFLICT updates only tag/source fields — re-running never un-reviews an
    approved note.
    """
    ingredient_ids = {
        name: iid
        for iid, name in conn.execute("SELECT id, name_zh FROM ingredient")
    }
    summary = TraditionImportSummary(rows_total=len(rows))
    for r in rows:
        iid = ingredient_ids.get(r.ingredient_zh)
        if iid is None:
            if r.ingredient_zh not in summary.unmatched_names:
                summary.unmatched_names.append(r.ingredient_zh)
            continue
        cur = conn.execute(
            """INSERT INTO ingredient_tradition_note
                   (ingredient_id, tag, note, source_title, source_url)
               VALUES (%(iid)s, %(tag)s, %(note)s, %(title)s, %(url)s)
               ON CONFLICT (ingredient_id, note)
               DO UPDATE SET tag = EXCLUDED.tag,
                             source_title = EXCLUDED.source_title,
                             source_url = EXCLUDED.source_url
               RETURNING (xmax = 0) AS inserted""",
            {
                "iid": iid, "tag": r.tag, "note": r.note,
                "title": r.source_title, "url": r.source_url,
            },
        )
        if cur.fetchone()[0]:
            summary.inserted += 1
        else:
            summary.updated += 1
    summary.unmatched_names.sort()
    return summary


def run_import(
    database_url: str, rows: list[TraditionRow], dry_run: bool = False
) -> TraditionImportSummary:
    """Execute the import in ONE transaction; dry-run rolls back at the end."""
    import psycopg  # lazy: unit tests run without the driver installed

    with psycopg.connect(database_url) as conn:
        try:
            summary = import_tradition(conn, rows)
            if dry_run:
                conn.rollback()
            else:
                conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return summary
