"""Manual recipe CSV import: parse + validate + match preview (pure, no DB).

Two files linked by recipe_id (UTF-8, BOM optional):

recipes.csv:           recipe_id,title,description,cook_time_min,servings,steps,tags,notes
recipe_ingredients.csv: recipe_id,ingredient_name,qty,unit,note,is_staple

- steps joined with ``||`` (1–30, each ≤300 chars); tags ``;``-separated (≤8, each ≤12).
- recipe_id ``^[A-Za-z0-9_-]{1,40}$``, unique per file; ``EXAMPLE``-prefixed ids refused.
- ingredient_name matched exactly against ingredient names/aliases/staple list via
  the same IngredientMatcher + normalize used by the crawler (no guessing).
- Forbidden-term rules (rules.FORBIDDEN_TERMS + recipe-only terms) apply to
  title/description/steps/tags/notes; any hit rejects that whole recipe.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from dataclasses import dataclass, field

from app.admin.rules import (
    find_recipe_forbidden_terms,
)
from app.crawler.allergens import scan_allergens
from app.crawler.matcher import IngredientMatcher
from app.crawler.parse import normalize

MAX_FILE_BYTES = 1_000_000
MAX_RECIPES = 500
RECIPE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
EXAMPLE_PREFIX = "EXAMPLE"
RECIPES_HEADER = [
    "recipe_id", "title", "description", "cook_time_min",
    "servings", "steps", "tags", "notes",
]
INGREDIENTS_HEADER = [
    "recipe_id", "ingredient_name", "qty", "unit", "note", "is_staple",
]
SOURCE_NAME = "濕疹食堂原創食譜"
SOURCE_LICENSE = "站方原創"
SOURCE_KIND = "manual"

_QTY_RE = re.compile(r"^\d+(?:\.\d+)?$")


class ImportFormatError(ValueError):
    """Whole-file failure: encoding, size, or wrong header."""


@dataclass
class FieldError:
    recipe_id: str | None
    row: int
    field: str
    message: str


@dataclass
class ImportItem:
    name: str
    qty: float | None
    unit: str | None
    note: str | None
    is_staple: bool
    row: int

    @property
    def raw_text(self) -> str:
        parts = [self.name]
        if self.qty is not None:
            qty = f"{self.qty:g}"
            parts.append(qty + (self.unit or ""))
        elif self.unit:
            parts.append(self.unit)
        if self.note:
            parts.append(self.note)
        return " ".join(parts)


@dataclass
class ParsedRecipe:
    external_key: str
    title: str
    description: str | None
    cook_time: int | None
    servings: int | None
    steps: list[str]
    tags: list[str]
    notes: str | None
    row: int
    items: list[ImportItem] = field(default_factory=list)


@dataclass
class MatchedRecipe:
    """A parsed recipe after deterministic matching + allergen scan."""
    recipe: ParsedRecipe
    matched: dict[int, list[ImportItem]]
    unmatched: list[str]
    unmatched_staples: list[str]
    allergen_hints: list[str]
    content_hash: str
    errors: list[FieldError] = field(default_factory=list)


@dataclass
class ParseResult:
    recipes: list[ParsedRecipe]
    errors: list[FieldError]           # file-level rows that failed to parse
    recipe_errors: dict[str, list[FieldError]]  # external_key -> per-recipe rejects


def decode_csv(data: bytes, label: str) -> str:
    if len(data) > MAX_FILE_BYTES:
        raise ImportFormatError(f"{label} 超過 1MB 上限。")
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportFormatError(f"{label} 不是有效的 UTF-8 檔案。") from exc


def _reader(text: str, header: list[str], label: str) -> csv.DictReader:
    stream = io.StringIO(text)
    reader = csv.reader(stream)
    try:
        first = next(reader)
    except StopIteration as exc:
        raise ImportFormatError(f"{label} 是空檔案。") from exc
    if [c.strip() for c in first] != header:
        raise ImportFormatError(
            f"{label} 表頭不正確，應為：{','.join(header)}。")
    return csv.DictReader(stream, fieldnames=header)


def parse_recipes_csv(text: str) -> tuple[list[ParsedRecipe], list[FieldError], dict[str, list[FieldError]]]:
    reader = _reader(text, RECIPES_HEADER, "recipes.csv")
    recipes: list[ParsedRecipe] = []
    row_errors: list[FieldError] = []
    recipe_errors: dict[str, list[FieldError]] = {}
    seen: set[str] = set()
    for n, row in enumerate(reader, start=2):
        if all((v or "").strip() == "" for v in row.values()):
            continue
        rid = (row.get("recipe_id") or "").strip()

        def err(field: str, msg: str, rid=rid, n=n) -> None:
            recipe_errors.setdefault(rid or f"row{n}", []).append(
                FieldError(rid or None, n, field, msg))
        if len(recipes) + sum(1 for k in recipe_errors) >= MAX_RECIPES:
            row_errors.append(FieldError(rid or None, n, "recipe_id", f"超過 {MAX_RECIPES} 筆食譜上限。"))
            break
        if not RECIPE_ID_RE.match(rid):
            row_errors.append(FieldError(rid or None, n, "recipe_id",
                "recipe_id 須為 1–40 個英數/底線/連字元。"))
            continue
        if rid.startswith(EXAMPLE_PREFIX):
            row_errors.append(FieldError(rid, n, "recipe_id",
                "recipe_id 不得以 EXAMPLE 開頭（範本保留）。"))
            continue
        if rid in seen:
            row_errors.append(FieldError(rid, n, "recipe_id",
                "recipe_id 重複。"))
            continue
        seen.add(rid)
        title = (row.get("title") or "").strip()
        if not title:
            err("title", "title 必填。")
        elif len(title) > 60:
            err("title", "title 不得超過 60 字。")
        description = (row.get("description") or "").strip() or None
        if description and len(description) > 200:
            err("description", "description 不得超過 200 字。")
        cook_raw = (row.get("cook_time_min") or "").strip()
        cook = None
        if cook_raw:
            if not cook_raw.isdigit() or not 1 <= int(cook_raw) <= 600:
                err("cook_time_min", "cook_time_min 須為 1–600 整數或留空。")
            else:
                cook = int(cook_raw)
        serv_raw = (row.get("servings") or "").strip()
        servings = None
        if serv_raw:
            if not serv_raw.isdigit() or not 1 <= int(serv_raw) <= 20:
                err("servings", "servings 須為 1–20 整數或留空。")
            else:
                servings = int(serv_raw)
        steps = [s.strip() for s in (row.get("steps") or "").split("||")]
        steps = [s for s in steps if s]
        if not 1 <= len(steps) <= 30:
            err("steps", "steps 須為 1–30 步（以 || 分隔）。")
        elif any(len(s) > 300 for s in steps):
            err("steps", "每一步不得超過 300 字。")
        tags = [t.strip() for t in (row.get("tags") or "").split(";") if t.strip()]
        if len(tags) > 8:
            err("tags", "tags 最多 8 個。")
        elif any(len(t) > 12 for t in tags):
            err("tags", "每個 tag 不得超過 12 字。")
        for t in tags:
            if t.startswith(("無", "不含")):
                err("tags", f"tag「{t}」不得以「無」「不含」開頭（無過敏原宣稱由系統推算）。")
        notes = (row.get("notes") or "").strip() or None
        if notes and len(notes) > 500:
            err("notes", "notes 不得超過 500 字。")
        for fname, text_ in (
            ("title", title), ("description", description or ""),
            ("steps", " ".join(steps)), ("tags", " ".join(tags)),
            ("notes", notes or ""),
        ):
            bad = find_recipe_forbidden_terms(text_)
            if bad:
                err(fname, "含禁用詞：" + "、".join(bad) + "。")
        if rid in recipe_errors:
            continue
        recipes.append(ParsedRecipe(
            external_key=rid, title=title, description=description,
            cook_time=cook, servings=servings, steps=steps, tags=tags,
            notes=notes, row=n))
    return recipes, row_errors, recipe_errors


def parse_ingredients_csv(text: str) -> tuple[dict[str, list[ImportItem]], list[FieldError]]:
    reader = _reader(text, INGREDIENTS_HEADER, "recipe_ingredients.csv")
    items: dict[str, list[ImportItem]] = {}
    errors: list[FieldError] = []
    for n, row in enumerate(reader, start=2):
        if all((v or "").strip() == "" for v in row.values()):
            continue
        rid = (row.get("recipe_id") or "").strip()
        name = (row.get("ingredient_name") or "").strip()
        bad = False
        if not name:
            errors.append(FieldError(rid or None, n, "ingredient_name", "ingredient_name 必填。"))
            bad = True
        qty = None
        qty_raw = (row.get("qty") or "").strip()
        if qty_raw:
            if not _QTY_RE.match(qty_raw):
                errors.append(FieldError(rid or None, n, "qty", "qty 須為 ≥0 數字（小數點用 .）或留空。"))
                bad = True
            else:
                qty = float(qty_raw)
        unit = (row.get("unit") or "").strip() or None
        if unit and len(unit) > 6:
            errors.append(FieldError(rid or None, n, "unit", "unit 不得超過 6 字。"))
            bad = True
        note = (row.get("note") or "").strip() or None
        if note and len(note) > 30:
            errors.append(FieldError(rid or None, n, "note", "note 不得超過 30 字。"))
            bad = True
        staple_flag = (row.get("is_staple") or "").strip().upper()
        if staple_flag not in ("", "Y", "N"):
            errors.append(FieldError(rid or None, n, "is_staple", "is_staple 須為 Y/N 或留空。"))
            bad = True
        if bad:
            continue
        items.setdefault(rid, []).append(ImportItem(
            name=name, qty=qty, unit=unit, note=note,
            is_staple=staple_flag == "Y", row=n))
    return items, errors


def parse_import(recipes_bytes: bytes, ingredients_bytes: bytes) -> ParseResult:
    """Parse + validate both files; per-recipe rejects do not block others."""
    recipes, row_errors, recipe_errors = parse_recipes_csv(
        decode_csv(recipes_bytes, "recipes.csv"))
    by_key = {r.external_key: r for r in recipes}
    items_map, item_errors = parse_ingredients_csv(
        decode_csv(ingredients_bytes, "recipe_ingredients.csv"))
    for rid, items in items_map.items():
        if rid not in by_key:
            for it in items:
                row_errors.append(FieldError(
                    rid, it.row, "recipe_id",
                    "recipe_ingredients.csv 中的 recipe_id 在 recipes.csv 不存在。"))
            continue
        by_key[rid].items.extend(items)
    for r in recipes:
        if len(r.items) < 2:
            recipe_errors.setdefault(r.external_key, []).append(FieldError(
                r.external_key, r.row, "ingredients", "每個食譜至少需要 2 行食材。"))
    recipes = [r for r in recipes if r.external_key not in recipe_errors]
    return ParseResult(recipes=recipes, errors=row_errors + item_errors,
                       recipe_errors=recipe_errors)


def content_hash(r: ParsedRecipe) -> str:
    payload = {
        "title": r.title, "description": r.description,
        "cook_time": r.cook_time, "servings": r.servings,
        "steps": r.steps, "tags": sorted(r.tags), "notes": r.notes,
        "items": [
            [i.name, i.qty, i.unit, i.note, i.is_staple]
            for i in sorted(r.items, key=lambda i: (i.name, i.qty or 0, i.unit or ""))
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def match_recipes(
    recipes: list[ParsedRecipe],
    matcher: IngredientMatcher,
    staples: set[str],
    keyword_map: dict[str, str],
) -> list[MatchedRecipe]:
    """Deterministic match; same semantics as crawler pipeline."""
    out: list[MatchedRecipe] = []
    for r in recipes:
        matched: dict[int, list[ImportItem]] = {}
        unmatched: list[str] = []
        unmatched_staples: list[str] = []
        for it in r.items:
            if normalize(it.name) in staples:
                it.is_staple = True
            iid = matcher.match(it.name)
            if iid is None:
                if normalize(it.name) in staples:
                    unmatched_staples.append(it.raw_text)
                else:
                    unmatched.append(it.raw_text)
            else:
                matched.setdefault(iid, []).append(it)
        hints = scan_allergens([i.raw_text for i in r.items], keyword_map)
        out.append(MatchedRecipe(
            recipe=r, matched=matched, unmatched=unmatched,
            unmatched_staples=unmatched_staples, allergen_hints=hints,
            content_hash=content_hash(r)))
    return out


# ---------------------------------------------------------------------------
# Writer layer (DB). Caller owns the transaction boundary.
# ---------------------------------------------------------------------------

@dataclass
class ImportStats:
    inserted: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    skipped_manual_status: int = 0
    rejected: int = 0
    unmatched_names: dict[str, int] = field(default_factory=dict)


def _cell(row, idx, key):
    return row[key] if isinstance(row, dict) else row[idx]


def _ensure_manual_source(conn) -> int:
    row = conn.execute(
        "SELECT id FROM data_source WHERE name = %s", (SOURCE_NAME,)).fetchone()
    if row:
        conn.execute(
            "UPDATE data_source SET license=%s, kind=%s, url=NULL WHERE id=%s",
            (SOURCE_LICENSE, SOURCE_KIND, _cell(row, 0, "id")))
        return _cell(row, 0, "id")
    return _cell(
        conn.execute(
            "INSERT INTO data_source (name,url,license,kind)"
            " VALUES (%s,NULL,%s,%s) RETURNING id",
            (SOURCE_NAME, SOURCE_LICENSE, SOURCE_KIND)).fetchone(), 0, "id")


def import_to_db(conn, matched: list[MatchedRecipe],
                 keyword_map: dict[str, str]) -> ImportStats:
    """Upsert by external_key in a single transaction (caller commits).

    published/rejected recipes are never overwritten (listed as skipped);
    unchanged content_hash → skipped; pending/draft → updated in place.
    """
    ds_id = _ensure_manual_source(conn)
    stats = ImportStats()
    for m in matched:
        r = m.recipe
        for t in m.unmatched:
            stats.unmatched_names[t] = stats.unmatched_names.get(t, 0) + 1
        row = conn.execute(
            "SELECT id, status, content_hash FROM recipe WHERE external_key=%s",
            (r.external_key,)).fetchone()
        if row and _cell(row, 2, "content_hash") == m.content_hash:
            stats.skipped_unchanged += 1
            continue
        if row and _cell(row, 1, "status") in ("published", "rejected"):
            stats.skipped_manual_status += 1
            continue
        if row:
            rid = _cell(row, 0, "id")
            conn.execute(
                "UPDATE recipe SET title=%s, description=%s, cook_time=%s,"
                " servings=%s, steps=%s, notes=%s, data_source_id=%s,"
                " content_hash=%s, unmatched_ingredients=%s,"
                " unmatched_staples=%s, allergen_hints=%s"
                " WHERE id=%s",
                (r.title, r.description, r.cook_time, r.servings, r.steps,
                 r.notes, ds_id, m.content_hash, m.unmatched,
                 m.unmatched_staples, m.allergen_hints, rid))
            conn.execute(
                "DELETE FROM recipe_ingredient WHERE recipe_id=%s", (rid,))
            conn.execute("DELETE FROM recipe_tag WHERE recipe_id=%s", (rid,))
            stats.updated += 1
        else:
            rid = _cell(conn.execute(
                "INSERT INTO recipe (title, description, cook_time, servings,"
                " steps, notes, is_original, external_key, data_source_id,"
                " status, content_hash, unmatched_ingredients,"
                " unmatched_staples, allergen_hints)"
                " VALUES (%s,%s,%s,%s,%s,%s,true,%s,%s,'pending_review',%s,%s,%s,%s)"
                " RETURNING id",
                (r.title, r.description, r.cook_time, r.servings, r.steps,
                 r.notes, r.external_key, ds_id, m.content_hash, m.unmatched,
                 m.unmatched_staples, m.allergen_hints)).fetchone(), 0, "id")
            stats.inserted += 1
            note = (f"原創食譜匯入；unmatched={len(m.unmatched)};"
                    f"unmatched_staples={len(m.unmatched_staples)};"
                    f"allergen_hints={','.join(m.allergen_hints) or 'none'}")
            conn.execute(
                "INSERT INTO review_queue (entity_type, entity_id, status,"
                " reviewer_note) VALUES ('recipe', %s, 'pending', %s)",
                (rid, note))
        conn.execute(
            "INSERT INTO audit_log (entity_type, entity_id, action, detail)"
            " VALUES ('recipe', %s, %s, %s)",
            (rid, "import_recipe",
             json.dumps({"external_key": r.external_key,
                         "updated": bool(row)}, ensure_ascii=False)))
        for iid, its in m.matched.items():
            qty = next((i.qty for i in its if i.qty is not None), None)
            unit = next((i.unit for i in its if i.unit), None)
            conn.execute(
                "INSERT INTO recipe_ingredient (recipe_id, ingredient_id,"
                " raw_text, qty, unit, is_staple) VALUES (%s,%s,%s,%s,%s,%s)"
                " ON CONFLICT (recipe_id, ingredient_id) DO UPDATE SET"
                " raw_text=EXCLUDED.raw_text, qty=EXCLUDED.qty,"
                " unit=EXCLUDED.unit, is_staple=EXCLUDED.is_staple",
                (rid, iid, "；".join(i.raw_text for i in its), qty, unit,
                 any(i.is_staple for i in its)))
        for tag in r.tags:
            conn.execute(
                "INSERT INTO recipe_tag (recipe_id, tag) VALUES (%s,%s)"
                " ON CONFLICT DO NOTHING", (rid, tag))
    return stats


def build_context(conn):
    """Load matcher/staples/keyword_map for match_recipes from a live conn."""
    from app.crawler.allergens import load_keyword_map
    from app.crawler.pipeline import ALLERGEN_CSV, STAPLE_CSV, load_staples

    matcher = IngredientMatcher.from_rows(
        (r["id"], r["name_zh"], r["aliases"]) if isinstance(r, dict) else r
        for r in conn.execute("SELECT id, name_zh, aliases FROM ingredient"))
    return matcher, load_staples(STAPLE_CSV), load_keyword_map(ALLERGEN_CSV)


def validate_recipe_form(
    *,
    title: str, description: str, cook_raw: str, servings_raw: str,
    steps: list[str], tags: list[str], notes: str,
    items: list[dict], external_key: str | None = None,
) -> tuple[ParsedRecipe | None, list[FieldError]]:
    """Validate admin new/edit form through the SAME rules as the CSV path.

    items: [{name, qty(raw str), unit, note, is_staple(bool)}]
    Returns (ParsedRecipe, []) or (None, errors).
    """
    errors: list[FieldError] = []
    title = (title or "").strip()
    if not title:
        errors.append(FieldError(None, 0, "title", "標題必填。"))
    elif len(title) > 60:
        errors.append(FieldError(None, 0, "title", "標題不得超過 60 字。"))
    description = (description or "").strip() or None
    if description and len(description) > 200:
        errors.append(FieldError(None, 0, "description", "描述不得超過 200 字。"))
    cook = None
    cook_raw = (cook_raw or "").strip()
    if cook_raw:
        if not cook_raw.isdigit() or not 1 <= int(cook_raw) <= 600:
            errors.append(FieldError(None, 0, "cook_time_min", "烹調時間須為 1–600 整數或留空。"))
        else:
            cook = int(cook_raw)
    servings = None
    servings_raw = (servings_raw or "").strip()
    if servings_raw:
        if not servings_raw.isdigit() or not 1 <= int(servings_raw) <= 20:
            errors.append(FieldError(None, 0, "servings", "份量須為 1–20 整數或留空。"))
        else:
            servings = int(servings_raw)
    steps = [s.strip() for s in steps if s.strip()]
    if not 1 <= len(steps) <= 30:
        errors.append(FieldError(None, 0, "steps", "步驟須為 1–30 步（每行一步）。"))
    elif any(len(s) > 300 for s in steps):
        errors.append(FieldError(None, 0, "steps", "每一步不得超過 300 字。"))
    tags = [t.strip() for t in tags if t.strip()]
    if len(tags) > 8:
        errors.append(FieldError(None, 0, "tags", "標籤最多 8 個。"))
    elif any(len(t) > 12 for t in tags):
        errors.append(FieldError(None, 0, "tags", "每個標籤不得超過 12 字。"))
    for t in tags:
        if t.startswith(("無", "不含")):
            errors.append(FieldError(None, 0, "tags",
                          f"標籤「{t}」不得以「無」「不含」開頭。"))
    notes = (notes or "").strip() or None
    if notes and len(notes) > 500:
        errors.append(FieldError(None, 0, "notes", "備註不得超過 500 字。"))
    for fname, text_ in (
        ("title", title), ("description", description or ""),
        ("steps", " ".join(steps)), ("tags", " ".join(tags)),
        ("notes", notes or ""),
    ):
        bad = find_recipe_forbidden_terms(text_)
        if bad:
            errors.append(FieldError(None, 0, fname,
                          "含禁用詞：" + "、".join(bad) + "。"))
    parsed_items: list[ImportItem] = []
    clean_items = [i for i in items if (i.get("name") or "").strip()]
    if len(clean_items) < 2:
        errors.append(FieldError(None, 0, "ingredients", "至少需要 2 行食材。"))
    for n, i in enumerate(clean_items):
        name = (i.get("name") or "").strip()
        qty = None
        qraw = str(i.get("qty") or "").strip()
        if qraw:
            if not _QTY_RE.match(qraw):
                errors.append(FieldError(None, n + 1, "qty", f"「{name}」數量須為 ≥0 數字。"))
                continue
            qty = float(qraw)
        unit = (i.get("unit") or "").strip() or None
        if unit and len(unit) > 6:
            errors.append(FieldError(None, n + 1, "unit", f"「{name}」單位過長。"))
            continue
        note = (i.get("note") or "").strip() or None
        if note and len(note) > 30:
            errors.append(FieldError(None, n + 1, "note", f"「{name}」備註過長。"))
            continue
        parsed_items.append(ImportItem(
            name=name, qty=qty, unit=unit, note=note,
            is_staple=bool(i.get("is_staple")), row=n + 1))
    if errors:
        return None, errors
    return ParsedRecipe(
        external_key=external_key or "", title=title, description=description,
        cook_time=cook, servings=servings, steps=steps, tags=tags,
        notes=notes, row=0, items=parsed_items), []


def load_staples_public(path=None) -> set[str]:
    from app.crawler.pipeline import STAPLE_CSV, load_staples
    return load_staples(path or STAPLE_CSV)
