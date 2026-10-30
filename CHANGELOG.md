# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-10-30

### Added

- **Recipe suggest API**: `POST /api/recipes/suggest` (`backend/app/api/recipes.py`, pure logic `backend/app/recipe_matching.py`) — 以手上食材（1–30 個 id，去重）配對食譜，回傳 coverage（未配對項目計入分母）、matched/missing、過敏原聯集（ingredient_allergen ∪ allergen_hints）、`allergen_warning`、`trigger_ingredients`、確定性排序（rank=coverage×score/100，NULL→0.5）；`exclude_allergens` 硬排除並計數（不靜默）；無法對映的 hint 列 `unknown_allergen_hints`＋warning；`warnings` 列出 trigger 或帶過敏原的所選食材。
- **`GET /api/recipes/{id}`** 詳情：已配對食材（raw_text/qty/unit/is_staple/allergens）、unmatched 清單、allergen union、draft 旗標、來源顯名與 license。
- **`recipe.unmatched_staples`**（migration `0004`）：常備調味料配對失敗者不擋發佈（published_recipe 只排除 `unmatched_ingredients` 非空），其致敏風險仍由 `allergen_hints` 關鍵字掃描覆蓋。
- **拆分器增強**：數量在前型（`1/2醋匙`→醋 1/2 匙、`3根香蕉`）、複合黏寫（`九層塔20克`、`五花300g`）；中文數字量詞需後接單位才算數（避免 `九層塔/五花肉` 誤拆）；亂碼字元原樣保留為 unmatched。
- **同義詞新增**（`ingredient_synonyms.csv`，全部指向既有 canonical）：蔥段/蔥花/青蔥→蔥，薑末/薑絲/薑片/嫩薑→薑，蒜末/蒜蓉/蒜片→蒜頭，五花肉/五花→豬五花腩，蝦乾→蝦米，蘿蔔/菜頭→白蘿蔔，中卷/乾魷魚/魷魚乾→魷魚，雞腿/土雞腿→雞腿肉，鴨→鴨肉，低筋麵粉→麵粉。
- **`data/reference/ingredients_to_add.md`**：人工審核用「建議新增食材」清單（名稱/建議分類/出現次數/備註）。
- **測試**：`test_recipe_matching.py`（7 個純邏輯測試：coverage 口徑、排序確定性、兩路致敏排除、staple 致敏、未知 hint、warnings、draft 判定）；整合測試：兩種可見性、unmatched 擋發佈、staple 不擋、422/404、分頁、OpenAPI、migration 0003+0004↔schema 同步、不覆蓋人工狀態。

### Changed

- **配對報告口徑**：配對率分母只算非 staple 項目，另列「staple 未配對 N 項」。客家食譜重跑：189 matched / 96 unmatched / 25 staple-unmatched，配對率 56.1%→**66.3%**，完全配對食譜 0→2。
- `recipe_ingredient` 的 `is_staple` 判定改用正規化後名稱比對。
- review_queue 的 reviewer_note 加入 unmatched_staples 數量。

## [0.5.0] - 2026-10-30

### Added

- **Recipe crawl pipeline** (`backend/app/crawler/`, PLAN.md §9 phase 4 groundwork): `base` (polite fetch: UA, timeout, retry, delay; content hash; stable slug), `hakka.py` (客委會 dataset adapter), `parse.py` (practic→材料/調味料 items with name/qty/unit incl. fractions, ranges, Chinese numerals, 少許/適量), `matcher.py` (exact + longest-token deterministic match, ambiguity→unmatched), `allergens.py` (allergen_keywords.csv scan over ALL raw item text incl. hidden forms), `pipeline.py` (single-transaction idempotent import).
- **CLI `python -m app.cli crawl-recipes --source hakka`**: `--download`, `--limit`, `--dry-run`, `--validate-only`; writes `data/reference/recipe_match_report_hakka.md` (match rate, top-50 unmatched, parse failures).
- **DB**: `recipe.unmatched_ingredients`, `recipe.allergen_hints`, `recipe.content_hash`; `published_recipe` view now also requires `cardinality(unmatched_ingredients)=0`; migration `docs/db/migrations/0003_recipe_pipeline.sql` kept in sync with `schema.sql`.
- **Write rules**: every recipe lands as `pending_review` (+ pending `review_queue` row with unmatched count and allergen hints), never auto-published; `published`/`rejected` rows are never overwritten on re-import; unchanged (source_url + content_hash) rows skipped; `crawl_job` records stats.
- **Reference data**: `data/reference/staple_ingredients.csv` (staple condiments → `is_staple`).
- **Tests**: `test_crawler.py` (12 unit tests — parse forms, match ambiguity, allergen hidden forms, staples, hash, manual-status protection) + integration tests (idempotent re-run, published_recipe gating, review_queue/crawl_job, migration↔schema sync).
- Hakka run: 32 recipes, 174 matched / 136 unmatched items (56.1%), 0 parse failures.

## [0.4.0] - 2026-10-30

### Added

- **Frontend MVP** (`frontend/`, PLAN.md §9 phase 3 features 1 & 3): Next.js 16 (App Router) + TypeScript + Tailwind CSS v4, mobile-first, 繁中, brand「濕疹食堂 Eczema Kitchen」, Noto Sans TC via `next/font/google`, design tokens extracted from `stitch_eczema_kitchen/eczema_kitchen/DESIGN.md` (canvas `#F8F5EF`, rating colours, 1200px max width).
- **Pages**: `/` home (large search box, entry cards, neutral quick links, rating explainer; 食譜配對 shown as 即將推出), `/ingredients?q=` search results, `/ingredients/[id]` detail (rating + reason, draft notice「此資料尚待人工審核」, allergens, per-100g nutrient table with source name, evidence links `rel="noopener noreferrer"`), `/categories` + `/categories/[id]` (rating filter chips, limit/offset pagination), `/about` (disclaimer, rating summary, TFDA 顯名聲明, audit process), styled 404, loading/error states, per-page metadata.
- **Components** (`src/components/`): `RatingBadge` (colour + icon + text, four states incl. 資料不足, no Level numbers), `AllergenTag`, `NutrientTable`, `WarningBanner`, `IngredientCard`, `Disclaimer` (every page footer), `SiteHeader` (desktop nav), `BottomNav` (mobile nav, ≥44px targets, no user/auth icons), `SearchBox`, `Pagination`.
- **API client** (`src/lib/api.ts`): server-side `fetch` with `API_BASE_URL` env (default `http://127.0.0.1:8000`), `cache: 'no-store'`, typed responses mirroring `backend/app/schemas.py`, `ApiError` + type guards; backend-unavailable renders a friendly warning instead of crashing.
- **Deployment**: `frontend/Dockerfile` (multi-stage, `output: 'standalone'`, non-root), `docker-compose.yml` `web` service (`API_BASE_URL=http://api:8000`, bound to `127.0.0.1:3000`), `.env.example` additions.
- **CI**: `frontend` job in `.github/workflows/ci.yml` (node 22: `npm ci`, eslint, `tsc --noEmit`, vitest, `next build`).
- **Tests**: vitest + jsdom — rating→label/icon/style mapping (incl. unrated fallback), API type guards, search-URL encoding, pagination math, RatingBadge render (no Level text).

### Changed

- Rendering runs in the classic dynamic model (`cacheComponents`/`partialPrefetching` disabled): API-backed routes are server-rendered on demand so `notFound()` returns real 404 statuses instead of streamed 200 shells; mobile `BottomNav` drops the active-state highlight to keep the layout static.

## [0.3.0] - 2026-10-30

### Added

- **Nutrition import pipeline** (`backend/app/nutrition.py`, PLAN.md §9 phase 1): TFDA 食品營養成分資料集（政府資料開放授權條款-第1版，顯名於 SOURCES.md 與日後關於頁）download → deterministic match → versioned reference CSV → DB import.
- **CLI `python -m app.cli import-nutrition`**: `--download` (fetch raw ZIP/CSV to `data/raw/`, git-ignored), `--build` (produce `data/reference/nutrition_tfda.csv` + `data/reference/nutrition_match_report.md`), `--validate-only`, `--dry-run`; default run upserts `data_source` (kind='nutrition'), `nutrient` (name+unit) and `ingredient_nutrient` (PK incl. source_id) in one idempotent transaction. Only existing ingredients are written — never creates ingredients nor touches `reviewed`/rating.
- **Deterministic matching rules**: NFKC + whitespace normalization, parenthesis- and `平均值`-stripped variants, exact match on 樣品名稱/俗名 vs seed name_zh/aliases (incl. synonyms), tiered name-over-alias priority, raw-only filter (processed categories/states/names excluded), unique candidate wins; multi-candidate falls back to the single official `平均值` sample, else skipped and reported.
- **Whitelisted nutrients**: 熱量、粗蛋白、粗脂肪、總碳水化合物、膳食纖維、鈉、鈣、鐵、鋅、維生素D、維生素E、EPA、DHA、α-次亞麻油酸；units normalized to g/mg/µg/kcal; non-numeric values skipped.
- **Generated data**: `data/reference/nutrition_tfda.csv` (908 rows, 76/163 seed ingredients matched) and `nutrition_match_report.md` (human-review list: no-candidate / all-processed / ambiguous).
- **Tests**: `backend/tests/test_nutrition.py` (30 unit tests — normalization, processed exclusion, match tiers, unit handling, CSV validation, "never writes ingredient/reviewed" via FakeConn); integration tests (TEST_DATABASE_URL-gated) for import idempotency, ingredient immutability and nutrients in the detail endpoint.

## [0.2.1] - 2026-10-29

### Fixed
- API: list/search queries crashed (`IndexError`) because `str.format` consumed the SQL literal `'{}'`; escaped as `'{{}}'` (found by CI integration tests; v0.2.0 list/search endpoints were broken).
- API: ingredient detail response omitted the required `disclaimer` field (500); it now defaults to the standard disclaimer string.

## [0.2.0] - 2026-10-29

### Added

- **Read API** (PLAN.md §6, ingredient + category parts): `GET /api/ingredients/search` (name/alias ILIKE via `aliases_text` trigram index, ranked exact > exact-alias > prefix > substring), `GET /api/ingredients/{id}` (rating, allergens, evidence, nutrients, disclaimer; `unrated` never leaks draft reasons), `GET /api/categories` (ingredient counts over visible rows only), `GET /api/categories/{id}/ingredients` (rating filter + pagination), `GET /api/allergens`. All read-only, pydantic response models, auto OpenAPI.
- **Draft visibility switch**: `INCLUDE_DRAFTS` env — when false every ingredient query reads the `published_ingredient` view only (unreviewed ids are 404); when true the `ingredient` table is used and payloads carry `draft` + `needs_senior_review`.
- **App config** (`app/config.py`): `APP_ENV` (development|production|test) and `CORS_ORIGINS` env vars; startup refuses `APP_ENV=production` + `INCLUDE_DRAFTS=true`; CORS middleware (GET only) added only when origins are configured.
- **DB pool**: `psycopg-pool` ConnectionPool (min 1 / max 5, dict_row) created in the FastAPI lifespan; `/health` checks through the pool.

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
