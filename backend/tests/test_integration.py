"""Integration tests — only run when TEST_DATABASE_URL is set.

Expected usage (CI): postgres:16 service + schema.sql + seed SQL applied, then
`TEST_DATABASE_URL=... pytest backend/tests`.
Locally: `docker compose up -d db`, then point TEST_DATABASE_URL at it.
"""

import os
from collections import Counter

import pytest
from conftest import REPO_ROOT, SCHEMA_SQL, SEED_CSV, SEED_SQL, SYNONYMS_CSV

psycopg = pytest.importorskip("psycopg")

TEST_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="TEST_DATABASE_URL not set — integration tests skipped"
)


@pytest.fixture(scope="session")
def db_url():
    return TEST_URL


def _apply_schema_if_missing(conn):
    exists = conn.execute("SELECT to_regclass('public.ingredient')").fetchone()[0]
    if exists is None:
        conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
        conn.execute(SEED_SQL.read_text(encoding="utf-8"))


def _table_counts(conn):
    tables = ["ingredient", "ingredient_allergen", "evidence", "data_source"]
    return {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in tables
    }


@pytest.fixture()
def fresh_db(db_url):
    """Ensure schema+seed exist and ingredient-domain tables are empty."""
    with psycopg.connect(db_url, autocommit=True) as conn:
        _apply_schema_if_missing(conn)
        conn.execute(
            "TRUNCATE evidence, ingredient_allergen, ingredient_nutrient, "
            "ingredient RESTART IDENTITY CASCADE"
        )
        conn.execute("DELETE FROM data_source WHERE kind = 'web'")
    return db_url


@pytest.fixture()
def seed_rows():
    from app.importer import (
        load_synonym_groups,
        merge_synonym_aliases,
        parse_seed_csv,
    )

    rows = parse_seed_csv(SEED_CSV)
    unmatched = merge_synonym_aliases(rows, load_synonym_groups(SYNONYMS_CSV))
    return rows, unmatched


def _import(db_url, rows, unmatched, dry_run=False):
    from app.importer import run_import

    return run_import(db_url, rows, unmatched_canonicals=unmatched, dry_run=dry_run)


def test_import_is_idempotent(fresh_db, seed_rows):
    rows, unmatched = seed_rows
    s1 = _import(fresh_db, rows, unmatched)
    assert s1.inserted == 163
    assert s1.updated == 0
    with psycopg.connect(fresh_db) as conn:
        counts_after_first = _table_counts(conn)

    s2 = _import(fresh_db, rows, unmatched)
    assert s2.inserted == 0
    assert s2.updated == 163
    with psycopg.connect(fresh_db) as conn:
        counts_after_second = _table_counts(conn)

    assert counts_after_first == counts_after_second
    assert counts_after_second["ingredient"] == 163


def test_import_never_publishes_anything(fresh_db, seed_rows):
    rows, unmatched = seed_rows
    _import(fresh_db, rows, unmatched)
    with psycopg.connect(fresh_db) as conn:
        (published,) = conn.execute(
            "SELECT count(*) FROM published_ingredient"
        ).fetchone()
        (reviewed,) = conn.execute(
            "SELECT count(*) FROM ingredient WHERE reviewed"
        ).fetchone()
    assert published == 0
    assert reviewed == 0


def test_dry_run_leaves_db_unchanged(fresh_db, seed_rows):
    rows, unmatched = seed_rows
    _import(fresh_db, rows, unmatched)
    with psycopg.connect(fresh_db) as conn:
        before = _table_counts(conn)
    _import(fresh_db, rows, unmatched, dry_run=True)
    with psycopg.connect(fresh_db) as conn:
        after = _table_counts(conn)
    assert before == after


def test_import_rating_counts_match_csv(fresh_db, seed_rows):
    rows, unmatched = seed_rows
    s = _import(fresh_db, rows, unmatched)
    expected = Counter(r.eczema_rating for r in rows)
    assert s.rating_counts == dict(expected)
    assert s.needs_senior_review == sum(r.needs_senior_review for r in rows)


def test_health_endpoint(fresh_db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", fresh_db)
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": True}


# --------------------------------------------------------------------------
# Read API (v0.2.0) — TestClient with per-test settings
# --------------------------------------------------------------------------


@pytest.fixture()
def imported_db(fresh_db, seed_rows):
    rows, unmatched = seed_rows
    _import(fresh_db, rows, unmatched)
    return fresh_db


def _client(db_url, drafts=False):
    """Context-managed TestClient bound to db_url with the given visibility."""
    from app.config import load_settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    settings = load_settings(
        {
            "DATABASE_URL": db_url,
            "APP_ENV": "test",
            "INCLUDE_DRAFTS": "true" if drafts else "false",
        }
    )
    return TestClient(create_app(settings))


def _ingredient_id(db_url, name):
    with psycopg.connect(db_url) as conn:
        return conn.execute(
            "SELECT id FROM ingredient WHERE name_zh = %s", (name,)
        ).fetchone()[0]


def _mark_reviewed(db_url, names):
    with psycopg.connect(db_url) as conn:
        conn.execute(
            "UPDATE ingredient SET reviewed = true, reviewed_at = now() "
            "WHERE name_zh = ANY(%s)",
            (list(names),),
        )


def test_drafts_hidden_by_default(imported_db):
    with _client(imported_db) as client:
        r = client.get("/api/ingredients/search", params={"q": "雞蛋"})
        assert r.status_code == 200
        assert r.json()["count"] == 0
        # an existing-but-unreviewed id is a 404, never a 200
        iid = _ingredient_id(imported_db, "雞蛋")
        assert client.get(f"/api/ingredients/{iid}").status_code == 404
        cats = client.get("/api/categories").json()
        assert all(c["ingredient_count"] == 0 for c in cats)


def test_reviewed_ingredients_visible(imported_db):
    _mark_reviewed(imported_db, ["雞蛋", "菜心", "西瓜"])
    with _client(imported_db) as client:
        r = client.get("/api/ingredients/search", params={"q": "雞蛋"})
        items = r.json()["items"]
        assert [i["name_zh"] for i in items] == ["雞蛋"]
        assert items[0]["draft"] is False
        assert items[0]["rating_label"] == "因人而異"

        iid = _ingredient_id(imported_db, "雞蛋")
        d = client.get(f"/api/ingredients/{iid}").json()
        assert d["draft"] is False
        assert d["rating_reason"]
        assert d["allergens"] and d["disclaimer"]
        assert d["needs_senior_review"] is None  # hidden when drafts are off

        # unrated + reviewed → draft reason nulled, label 資料不足
        wid = _ingredient_id(imported_db, "西瓜")
        d2 = client.get(f"/api/ingredients/{wid}").json()
        assert d2["eczema_rating"] == "unrated"
        assert d2["rating_reason"] is None
        assert d2["rating_label"] == "資料不足"

        # unreviewed stays hidden even though the row exists
        hid = _ingredient_id(imported_db, "芋頭")
        assert client.get(f"/api/ingredients/{hid}").status_code == 404

        cats = {
            c["name_zh"]: c["ingredient_count"]
            for c in client.get("/api/categories").json()
        }
        assert cats["蛋奶"] == 1
        assert cats["蔬菜"] == 1
        assert cats["水果"] == 1


def test_include_drafts_shows_everything(imported_db):
    with _client(imported_db, drafts=True) as client:
        r = client.get("/api/ingredients/search", params={"q": "雞蛋"})
        item = r.json()["items"][0]
        assert item["draft"] is True
        iid = _ingredient_id(imported_db, "雞蛋")
        d = client.get(f"/api/ingredients/{iid}").json()
        assert d["draft"] is True
        assert d["needs_senior_review"] is True  # 雞蛋 flagged in the CSV
        cats_total = sum(
            c["ingredient_count"] for c in client.get("/api/categories").json()
        )
        assert cats_total == 163


def test_search_ranking_and_aliases(imported_db):
    with _client(imported_db, drafts=True) as client:
        items = client.get(
            "/api/ingredients/search", params={"q": "雞蛋"}
        ).json()["items"]
        assert items[0]["name_zh"] == "雞蛋"  # exact name match first
        # alias hit: 番茄 carries the alias 蕃茄
        res = client.get("/api/ingredients/search", params={"q": "蕃茄"}).json()
        assert any(i["name_zh"] == "番茄" for i in res["items"])


@pytest.mark.parametrize("q", ["%", "_", "%%", "100%"])
def test_search_escapes_like_metachars(imported_db, q):
    with _client(imported_db, drafts=True) as client:
        res = client.get("/api/ingredients/search", params={"q": q}).json()
        assert res["count"] == 0


@pytest.mark.parametrize("q", ["", "   ", "x" * 51])
def test_search_q_validation(imported_db, q):
    with _client(imported_db, drafts=True) as client:
        r = client.get("/api/ingredients/search", params={"q": q})
        assert r.status_code == 422


def test_category_ingredients_filter_and_pagination(imported_db):
    with _client(imported_db, drafts=True) as client:
        cats = {c["name_zh"]: c["id"] for c in client.get("/api/categories").json()}
        cid = cats["蔬菜"]
        r = client.get(
            f"/api/categories/{cid}/ingredients",
            params={"rating": "caution", "limit": 5, "offset": 0},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["category"]["id"] == cid
        assert len(body["items"]) <= 5
        assert all(i["eczema_rating"] == "caution" for i in body["items"])
        with psycopg.connect(imported_db) as conn:
            expected = conn.execute(
                "SELECT count(*) FROM ingredient "
                "WHERE category_id = %s AND eczema_rating = 'caution'",
                (cid,),
            ).fetchone()[0]
        assert body["total"] == expected
        if expected > 1:
            r2 = client.get(
                f"/api/categories/{cid}/ingredients",
                params={"rating": "caution", "limit": 5, "offset": 1},
            ).json()
            assert r2["items"][0]["id"] != body["items"][0]["id"]
        assert (
            client.get(
                f"/api/categories/{cid}/ingredients", params={"rating": "bogus"}
            ).status_code
            == 422
        )
        assert client.get("/api/categories/999999/ingredients").status_code == 404


def test_allergens_endpoint(imported_db):
    with _client(imported_db) as client:
        r = client.get("/api/allergens")
        assert r.status_code == 200
        assert len(r.json()) == 13
        assert {a["name_zh"] for a in r.json()} >= {"蛋", "奶", "花粉交叉"}


# --------------------------------------------------------------------------
# Nutrition import (v0.3.0) — reference CSV → ingredient_nutrient
# --------------------------------------------------------------------------

NUTRITION_CSV = (
    REPO_ROOT / "data" / "reference" / "nutrition_tfda.csv"
)


def _import_nutrition(db_url, dry_run=False):
    from app.nutrition import parse_reference_csv
    from app.nutrition import run_import as run_nutrition

    return run_nutrition(db_url, parse_reference_csv(NUTRITION_CSV), dry_run)


@pytest.fixture()
def nutrition_db(imported_db):
    _import_nutrition(imported_db)
    return imported_db


def test_nutrition_import_is_idempotent(nutrition_db):
    with psycopg.connect(nutrition_db) as conn:
        counts = {
            t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in ("ingredient", "nutrient", "ingredient_nutrient")
        }
    _import_nutrition(nutrition_db)
    with psycopg.connect(nutrition_db) as conn:
        for t, n in counts.items():
            assert conn.execute(
                f"SELECT count(*) FROM {t}"
            ).fetchone()[0] == n


def test_nutrition_import_never_touches_ingredient(nutrition_db):
    with psycopg.connect(nutrition_db) as conn:
        snapshot = conn.execute(
            "SELECT id, name_zh, eczema_rating, reviewed FROM ingredient "
            "ORDER BY id"
        ).fetchall()
    _import_nutrition(nutrition_db)
    with psycopg.connect(nutrition_db) as conn:
        assert (
            conn.execute(
                "SELECT id, name_zh, eczema_rating, reviewed "
                "FROM ingredient ORDER BY id"
            ).fetchall()
            == snapshot
        )
        (src,) = conn.execute(
            "SELECT count(*) FROM data_source "
            "WHERE kind = 'nutrition' AND name LIKE 'TFDA%'"
        ).fetchone()
        assert src == 1
        # only whitelisted units
        bad = conn.execute(
            "SELECT count(*) FROM nutrient WHERE unit NOT IN "
            "('g', 'mg', 'µg', 'kcal')"
        ).fetchone()[0]
        assert bad == 0


def test_detail_endpoint_returns_nutrients(nutrition_db):
    with psycopg.connect(nutrition_db) as conn:
        row = conn.execute(
            "SELECT i.id FROM ingredient i "
            "JOIN ingredient_nutrient n ON n.ingredient_id = i.id "
            "LIMIT 1"
        ).fetchone()
    iid = row[0]
    with _client(nutrition_db, drafts=True) as client:
        d = client.get(f"/api/ingredients/{iid}").json()
    assert d["nutrients"], "expected nutrients in detail payload"
    assert all(n["source"].startswith("TFDA") for n in d["nutrients"])
    assert all(n["unit"] in {"g", "mg", "µg", "kcal"} for n in d["nutrients"])
