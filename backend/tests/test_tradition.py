"""Unit tests for the tradition-notes importer (DB-free)."""

import re
import textwrap

import pytest
from app.tradition import (
    ALLOWED_TAGS,
    TraditionRow,
    TraditionValidationError,
    import_tradition,
    parse_tradition_csv,
)
from conftest import REPO_ROOT

HEADER = "ingredient_zh,tag,note,source_title,source_url"
TRADITION_CSV = REPO_ROOT / "data" / "seed" / "tradition_notes.csv"


def write_csv(tmp_path, body: str, header: str = HEADER):
    p = tmp_path / "trad.csv"
    p.write_text(header + "\n" + textwrap.dedent(body), encoding="utf-8")
    return p


def test_parse_minimal_row(tmp_path):
    p = write_csv(tmp_path, "蝦,fawu,中醫認為宜留意,書名,https://a.example/x")
    (r,) = parse_tradition_csv(p)
    assert (r.ingredient_zh, r.tag, r.note) == ("蝦", "fawu", "中醫認為宜留意")
    assert r.source_url == "https://a.example/x"


def test_header_must_be_exact(tmp_path):
    p = write_csv(tmp_path, "蝦,fawu,n,t,https://a.example/x",
                  header="ingredient_zh,tag,note,source_title")
    with pytest.raises(TraditionValidationError, match="header"):
        parse_tradition_csv(p)


def test_bad_tag_rejected(tmp_path):
    p = write_csv(tmp_path, "蝦,spicy,n,t,https://a.example/x")
    with pytest.raises(TraditionValidationError, match=r"row 2.*tag"):
        parse_tradition_csv(p)


def test_empty_note_rejected(tmp_path):
    p = write_csv(tmp_path, "蝦,fawu,,t,https://a.example/x")
    with pytest.raises(TraditionValidationError, match=r"row 2.*note"):
        parse_tradition_csv(p)


def test_non_https_url_rejected(tmp_path):
    for url in ["http://a.example/x", "a.example/x", ""]:
        p = write_csv(tmp_path, f"蝦,fawu,n,t,{url}")
        with pytest.raises(TraditionValidationError, match=r"row 2.*https"):
            parse_tradition_csv(p)


def test_empty_source_title_rejected(tmp_path):
    p = write_csv(tmp_path, "蝦,fawu,n,,https://a.example/x")
    with pytest.raises(TraditionValidationError, match=r"row 2.*source_title"):
        parse_tradition_csv(p)


def test_forbidden_terms_rejected(tmp_path):
    p = write_csv(tmp_path, "蝦,fawu,此物可治療濕疹,t,https://a.example/x")
    with pytest.raises(TraditionValidationError, match=r"row 2.*forbidden"):
        parse_tradition_csv(p)


# --------------------------------------------------------------------------
# import_tradition against a fake connection
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
    """Records SQL; serves the ingredient name lookup and RETURNING xmax."""

    def __init__(self, ingredients, insert_result=True):
        self.ingredients = ingredients  # {name_zh: id}
        self.insert_result = insert_result
        self.queries = []

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        self.queries.append(s)
        if s.startswith("select id, name_zh from ingredient"):
            return FakeResult([(i, n) for n, i in self.ingredients.items()])
        if "returning (xmax = 0)" in s:
            return FakeResult([(self.insert_result,)])
        return FakeResult()


def _row(name="蝦"):
    return TraditionRow(
        row_no=2, ingredient_zh=name, tag="fawu", note="n",
        source_title="t", source_url="https://a.example/x",
    )


def test_import_never_writes_reviewed():
    conn = FakeConn({"蝦": 1})
    s = import_tradition(conn, [_row()])
    assert s.inserted == 1 and not s.unmatched_names
    dml = [q for q in conn.queries if q.startswith(("insert", "update"))]
    for q in dml:
        assert not re.search(r"\breviewed\b", q), q
    # ON CONFLICT updates only tag/source fields
    ins = next(q for q in conn.queries if "on conflict" in q)
    assert "do update set tag" in ins and "reviewed" not in ins


def test_import_unmatched_reported_not_fatal():
    conn = FakeConn({"蝦": 1})
    s = import_tradition(conn, [_row("蝦"), _row("不存在食材"), _row("不存在食材")])
    assert s.inserted == 1
    assert s.unmatched_names == ["不存在食材"]


def test_real_csv_validates_and_tags_allowed():
    rows = parse_tradition_csv(TRADITION_CSV)
    assert len(rows) == 34
    assert {r.tag for r in rows} <= ALLOWED_TAGS
    assert all(r.source_url.startswith("https://") for r in rows)
