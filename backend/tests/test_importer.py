"""Unit tests for seed parsing/validation/allergen mapping/synonym merge.

All tests are DB-free. A FakeConn simulates psycopg for import_seed so we can
assert idempotent upserts and that `reviewed` is never written.
"""

import re
import textwrap

import pytest
from app.importer import (
    ALLERGEN_TOKEN_MAP,
    SeedRow,
    SeedValidationError,
    import_seed,
    load_seed_category_names,
    load_synonym_groups,
    merge_synonym_aliases,
    parse_seed_csv,
    validate_categories,
)
from conftest import SEED_CSV, SEED_SQL, SYNONYMS_CSV

HEADER = (
    "category_zh,name_zh,name_en,aliases,eczema_rating,rating_reason,"
    "allergens,source_urls,needs_senior_review,notes"
)


def write_csv(tmp_path, body: str):
    p = tmp_path / "seed.csv"
    p.write_text(HEADER + "\n" + textwrap.dedent(body), encoding="utf-8")
    return p


def test_parse_minimal_row(tmp_path):
    p = write_csv(tmp_path, "蔬菜,白菜,bok choy,小白菜,suitable,一般適合,,,false,")
    rows = parse_seed_csv(p)
    assert len(rows) == 1
    r = rows[0]
    assert r.row_no == 2
    assert (r.category_zh, r.name_zh, r.name_en) == ("蔬菜", "白菜", "bok choy")
    assert r.aliases == ["小白菜"]
    assert r.eczema_rating == "suitable"
    assert r.allergen_tokens == []
    assert r.source_urls == []
    assert r.needs_senior_review is False


def test_semicolon_fields_split(tmp_path):
    p = write_csv(
        tmp_path,
        "豆類及豆製品,豆腐,tofu,豆府;豆腐,caution,大豆過敏原之一,大豆;高組織胺,"
        "https://a.example/x;https://b.example/y,true,",
    )
    (r,) = parse_seed_csv(p)
    assert r.aliases == ["豆府"]  # alias equal to name_zh is dropped
    assert r.allergen_tokens == ["大豆", "高組織胺"]
    assert r.source_urls == ["https://a.example/x", "https://b.example/y"]
    assert r.needs_senior_review is True


def test_invalid_rating_raises_with_row_no(tmp_path):
    p = write_csv(tmp_path, "蔬菜,白菜,,,ok,一般適合,,,,")
    with pytest.raises(SeedValidationError, match=r"row 2"):
        parse_seed_csv(p)


def test_caution_without_reason_raises(tmp_path):
    p = write_csv(tmp_path, "蛋奶,雞蛋,egg,,caution,,蛋,,,")
    with pytest.raises(SeedValidationError, match=r"row 2.*rating_reason"):
        parse_seed_csv(p)


def test_trigger_without_reason_raises(tmp_path):
    p = write_csv(tmp_path, "蛋奶,雞蛋,egg,,trigger,,蛋,,,")
    with pytest.raises(SeedValidationError, match=r"row 2.*rating_reason"):
        parse_seed_csv(p)


def test_duplicate_name_raises(tmp_path):
    p = write_csv(
        tmp_path,
        "蔬菜,白菜,,,suitable,r,,,,\n蔬菜,白菜,,,suitable,r,,,,",
    )
    with pytest.raises(SeedValidationError, match=r"row 3.*duplicate"):
        parse_seed_csv(p)


def test_unknown_allergen_token_raises(tmp_path):
    p = write_csv(tmp_path, "海鮮,蝦,shrimp,,caution,r,甲殼類;貝類,,,")
    with pytest.raises(SeedValidationError, match=r"row 2.*unknown allergen"):
        parse_seed_csv(p)


def test_validate_categories(tmp_path):
    p = write_csv(tmp_path, "仙豆,白菜,,,suitable,r,,,,")
    rows = parse_seed_csv(p)
    with pytest.raises(SeedValidationError, match=r"row 2.*unknown category"):
        validate_categories(rows, {"蔬菜", "肉類"})


def test_allergen_token_map_covers_csv_tokens():
    expected = {
        "蛋", "奶", "花生", "堅果", "大豆", "小麥", "魚", "甲殼類", "芝麻",
        "高組織胺", "高水楊酸", "高鎳", "花粉交叉",
    }
    assert expected == set(ALLERGEN_TOKEN_MAP)
    # spot-check non-identity mappings
    assert ALLERGEN_TOKEN_MAP["堅果"] == "堅果(樹堅果)"
    assert ALLERGEN_TOKEN_MAP["高組織胺"] == "組織胺"
    assert ALLERGEN_TOKEN_MAP["花粉交叉"] == "花粉交叉"


def test_load_seed_category_names():
    names = load_seed_category_names(SEED_SQL)
    assert {"肉類", "蔬菜", "豆類及豆製品", "其他"} <= names
    assert len(names) == 12


def test_merge_synonym_aliases_by_name_and_alias():
    rows = [
        SeedRow(2, "蔬菜", "番茄", "tomato", ["蕃茄"], "suitable", "r", [], [], False, ""),
        SeedRow(3, "蔬菜", "生菜", "lettuce", [], "suitable", "r", [], [], False, ""),
    ]
    groups = {"番茄": ["tomato", "西紅柿"], "紅蘿蔔": ["胡蘿蔔"]}
    unmatched = merge_synonym_aliases(rows, groups)
    assert "蕃茄" in rows[0].aliases and "西紅柿" in rows[0].aliases
    assert rows[0].aliases.count("tomato") == 1  # deduped
    assert unmatched == 1  # 紅蘿蔔 matched nothing
    # group that matched via an alias also pulls in its canonical name
    rows2 = [SeedRow(2, "蔬菜", "矮瓜", "", ["茄子"], "suitable", "r", [], [], False, "")]
    merge_synonym_aliases(rows2, {"茄子": ["矮瓜", "eggplant"]})
    assert "eggplant" in rows2[0].aliases


# --------------------------------------------------------------------------
# import_seed against a fake connection (no psycopg, no DB)
# --------------------------------------------------------------------------


class FakeResult:
    def __init__(self, rows=(), rowcount=1):
        self._rows = list(rows)
        self.rowcount = rowcount

    def __iter__(self):
        return iter(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    """Records executed SQL; returns canned rows for the lookups import_seed makes."""

    def __init__(self, categories, allergens, existing=None):
        self.categories = categories  # [(id, name_zh)]
        self.allergens = allergens  # [(id, name_zh)]
        self.existing = existing or {}  # name_zh -> ingredient id
        self.queries = []
        self._next_iid = 100

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        self.queries.append(s)
        if s.startswith("select id, name_zh from food_category"):
            return FakeResult(self.categories)
        if s.startswith("select id, name_zh from allergen"):
            return FakeResult(self.allergens)
        if s.startswith("select id from ingredient where name_zh"):
            iid = self.existing.get(params[0])
            return FakeResult([(iid,)] if iid else [])
        if s.startswith("select id from data_source where name"):
            return FakeResult([(1,)])
        if "returning id" in s:
            self._next_iid += 1
            return FakeResult([(self._next_iid,)])
        return FakeResult()


def _row(name="雞蛋", rating="caution", tokens=("蛋",), urls=()):
    return SeedRow(
        row_no=2, category_zh="蛋奶", name_zh=name, name_en="egg",
        aliases=["蛋"], eczema_rating=rating, rating_reason="r",
        allergen_tokens=list(tokens), source_urls=list(urls),
        needs_senior_review=False, notes="",
    )


def test_import_seed_never_writes_reviewed():
    conn = FakeConn(categories=[(1, "蛋奶")], allergens=[(1, "蛋")])
    summary = import_seed(conn, [_row()])
    assert summary.inserted == 1
    assert summary.allergen_links == 1
    dml = [q for q in conn.queries if q.startswith(("insert", "update"))]
    assert dml, "expected DML statements"
    for q in dml:
        assert not re.search(r"\breviewed(_at)?\b", q), q


def test_import_seed_update_path_and_evidence_conflict():
    conn = FakeConn(
        categories=[(1, "蛋奶")],
        allergens=[(1, "蛋")],
        existing={"雞蛋": 7},
    )
    row = _row(urls=["https://www.cfs.gov.hk/a", "https://x.example/b"])
    summary = import_seed(conn, [row])
    assert summary.updated == 1 and summary.inserted == 0
    # allergen links are replaced in the same transaction: DELETE then INSERT
    assert any(
        q.startswith("delete from ingredient_allergen") for q in conn.queries
    )
    evidence_inserts = [
        q for q in conn.queries if q.startswith("insert into evidence")
    ]
    assert len(evidence_inserts) == 2
    assert all("on conflict" in q for q in evidence_inserts)


def test_import_seed_rejects_missing_allergen_rows():
    conn = FakeConn(categories=[(1, "蛋奶")], allergens=[])
    with pytest.raises(SeedValidationError, match="allergen"):
        import_seed(conn, [_row()])


# --------------------------------------------------------------------------
# real seed CSV (must stay valid — importer relies on these invariants)
# --------------------------------------------------------------------------


def test_real_csv_parses_and_is_valid():
    rows = parse_seed_csv(SEED_CSV)
    assert len(rows) == 163
    # every caution/trigger carries a reason (parse_seed_csv already enforces)
    assert all(
        r.rating_reason
        for r in rows
        if r.eczema_rating in {"caution", "trigger"}
    )
    # no trigger rows in the draft (see data/seed/README.md)
    assert not [r for r in rows if r.eczema_rating == "trigger"]
    # every category exists in the seed SQL
    validate_categories(rows, load_seed_category_names(SEED_SQL))
    # importer never marks anything reviewed: nothing in the CSV schema can —
    # assert the parsed model has no reviewed field at all
    assert not hasattr(rows[0], "reviewed")


def test_real_csv_needs_senior_review_count():
    rows = parse_seed_csv(SEED_CSV)
    assert sum(r.needs_senior_review for r in rows) == 71


def test_real_csv_synonym_merge_reports_unmatched():
    rows = parse_seed_csv(SEED_CSV)
    groups = load_synonym_groups(SYNONYMS_CSV)
    unmatched = merge_synonym_aliases(rows, groups)
    # informative, not a failure — print shows how many canonicals found no row
    assert 0 <= unmatched <= len(groups)
    merged = sum(len(r.aliases) for r in rows)
    assert merged > 163  # merge actually added aliases
