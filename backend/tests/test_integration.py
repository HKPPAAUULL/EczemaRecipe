"""Integration tests — only run when TEST_DATABASE_URL is set.

Expected usage (CI): postgres:16 service + schema.sql + seed SQL applied, then
`TEST_DATABASE_URL=... pytest backend/tests`.
Locally: `docker compose up -d db`, then point TEST_DATABASE_URL at it.
"""

import os
from collections import Counter

import pytest
from conftest import SCHEMA_SQL, SEED_CSV, SEED_SQL, SYNONYMS_CSV

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

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": True}
