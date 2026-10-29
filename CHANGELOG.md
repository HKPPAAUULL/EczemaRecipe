# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-10-29

### Fixed
- Schema: alias trigram index used the non-IMMUTABLE `array_to_string`; replaced with an IMMUTABLE wrapper `aliases_text()` (found by CI on real PostgreSQL 16; v0.1.0 schema did not apply).

## [0.1.0] - 2026-10-29

### Added

- **Database schema** (`docs/db/schema.sql`): PostgreSQL 16 DDL — `data_source`, `food_category`, `ingredient`, `nutrient`, `ingredient_nutrient`, `allergen`, `ingredient_allergen`, `evidence`, `recipe`, `recipe_ingredient`, `recipe_tag`, `crawl_job`, `review_queue`; enums for rating/status/allergen type/severity; `pg_trgm` indexes for name + alias search; `published_ingredient` / `published_recipe` views (only human-reviewed content is public).
- **Seed SQL** (`docs/db/seed_categories_allergens.sql`): 12 food categories and 13 allergen rows (9 major allergens + histamine/salicylate/nickel + pollen cross-reactivity).
- **Reference data** (`data/reference/`): `allergen_keywords.csv` (471 HK/TW/EN keywords incl. hidden forms) and `ingredient_synonyms.csv` (635 alias rows for 270 canonical ingredients).
- **Draft ingredient seed** (`data/seed/ingredients_draft.csv`): 163 rated ingredients — all `reviewed=false` drafts pending human review.
- **Backend** (`backend/`): FastAPI app with `GET /health` (checks DB via `SELECT 1`); psycopg 3 with plain SQL, no ORM; `Dockerfile` on `python:3.12-slim` running as non-root.
- **Seed importer** (`python -m app.cli import-seed`): validates the draft CSV (rating rules, unique names, known allergen tokens, known categories), merges synonym aliases, upserts ingredients + allergen links + `data_source`/`evidence` per source URL in one transaction; `--dry-run` and `--validate-only` flags.
- **Docker Compose** (`docker-compose.yml`): `db` (postgres:16, schema+seed init scripts, healthcheck, port bound to 127.0.0.1 only, `pgdata` volume) and `api` (builds `./backend`, waits for healthy db). Credentials via `.env` (see `.env.example`).
- **Tests** (`backend/tests/`): unit tests for parsing/validation/allergen mapping/synonym merge/"never sets reviewed" plus integration tests gated on `TEST_DATABASE_URL` (idempotent double import, `published_ingredient` empty, dry-run rollback, `/health`).
- **CI** (`.github/workflows/ci.yml`): postgres:16 service, ruff lint, schema+seed apply, CSV validate-only, pytest.
- Repo housekeeping: `.gitignore`, `.env.example`.
