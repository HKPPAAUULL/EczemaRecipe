"""Command-line entry: ``python -m app.cli import-seed|import-nutrition``.

Run as ``python -m app.cli`` from backend/ (or with backend/ on PYTHONPATH);
default data paths resolve relative to the repo root regardless of cwd.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.config import get_database_url
from app.importer import (
    DEFAULT_CSV,
    DEFAULT_SEED_SQL,
    DEFAULT_SYNONYMS_CSV,
    SeedValidationError,
    load_seed_category_names,
    load_synonym_groups,
    merge_synonym_aliases,
    parse_seed_csv,
    run_import,
    validate_categories,
)
from app.nutrition import (
    DEFAULT_MATCH_REPORT,
    DEFAULT_NUTRITION_CSV,
    DEFAULT_RAW_CSV,
    TFDA_DOWNLOAD_URL,
    NutritionValidationError,
    build_reference,
    download_raw,
    parse_reference_csv,
)
from app.nutrition import (
    run_import as run_nutrition_import,
)


def _cmd_import_seed(args: argparse.Namespace) -> int:
    csv_path = Path(args.csv)
    if not csv_path.is_file():
        print(f"error: CSV not found: {csv_path}", file=sys.stderr)
        return 2

    rows = parse_seed_csv(csv_path)

    # Offline category check against the seed SQL (same names as the DB seeds).
    categories = load_seed_category_names(args.seed_sql)
    validate_categories(rows, categories)

    groups = load_synonym_groups(args.synonyms) if Path(args.synonyms).is_file() else {}
    unmatched = merge_synonym_aliases(rows, groups)

    if args.validate_only:
        print(
            f"validate-only OK: {len(rows)} rows parsed from {csv_path}; "
            f"{len(groups)} synonym canonicals ({unmatched} unmatched)"
        )
        return 0

    try:
        database_url = get_database_url()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    summary = run_import(
        database_url, rows, unmatched_canonicals=unmatched, dry_run=args.dry_run
    )
    print(summary.format(dry_run=args.dry_run))
    return 0


def _cmd_import_nutrition(args: argparse.Namespace) -> int:
    if args.download:
        csv_path = download_raw(TFDA_DOWNLOAD_URL, Path(args.raw).parent)
        print(f"downloaded: {csv_path}")

    if args.build:
        matches = build_reference(
            args.raw, args.seed_csv, args.synonyms, args.csv, args.report
        )
        ok = sum(1 for m in matches if m.sample is not None)
        print(
            f"build OK: {ok}/{len(matches)} ingredients matched -> {args.csv}; "
            f"report -> {args.report}"
        )

    if args.validate_only:
        rows = parse_reference_csv(args.csv)
        print(f"validate-only OK: {len(rows)} rows parsed from {args.csv}")
        return 0

    if args.download or args.build:
        return 0

    rows = parse_reference_csv(args.csv)
    try:
        database_url = get_database_url()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = run_nutrition_import(database_url, rows, dry_run=args.dry_run)
    print(summary.format(dry_run=args.dry_run))
    return 0


def _cmd_crawl_recipes(args: argparse.Namespace) -> int:
    from app.crawler import hakka
    from app.crawler.pipeline import REPORT_MD, run_import, write_report

    raw = Path(args.raw) if args.raw else hakka.DEFAULT_RAW
    if args.download:
        print(f"downloaded: {hakka.download_raw(raw)}")
    records = hakka.load_records(raw, limit=args.limit)
    if args.validate_only:
        from app.crawler.pipeline import CrawlStats, import_recipes  # noqa: F401
        stats = CrawlStats(fetched=len(records))
        stats.parse_failed = sum(1 for r in records if r.parse_failed)
        items = sum(len(r.items) + len(r.seasoning_items) for r in records)
        print(
            f"validate-only OK: {len(records)} recipes, {items} items, "
            f"{stats.parse_failed} parse failures"
        )
        return 0
    try:
        database_url = get_database_url()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    stats = run_import(
        database_url, hakka.SOURCE_NAME, hakka.SOURCE_URL,
        hakka.SOURCE_LICENSE, records, dry_run=args.dry_run,
    )
    write_report(records, stats, args.report or REPORT_MD)
    print(
        f"crawl-recipes ({args.source})"
        f"{' dry-run: rolled back' if args.dry_run else ''}: "
        f"fetched={stats.fetched} inserted={stats.inserted} "
        f"updated={stats.updated} unchanged={stats.skipped_unchanged} "
        f"manual-status-skipped={stats.skipped_manual_status} "
        f"parse_failed={stats.parse_failed} "
        f"matched={stats.matched_items} unmatched={stats.unmatched_items} "
        f"match_rate={stats.match_rate:.1%}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("import-seed", help="import data/seed/ingredients_draft.csv into the DB")
    p.add_argument("--csv", default=str(DEFAULT_CSV), help="path to the seed CSV")
    p.add_argument("--synonyms", default=str(DEFAULT_SYNONYMS_CSV), help="synonym CSV path")
    p.add_argument("--seed-sql", default=str(DEFAULT_SEED_SQL), help="seed SQL file (category check)")
    p.add_argument("--dry-run", action="store_true", help="run in one transaction then roll back")
    p.add_argument("--validate-only", action="store_true", help="validate CSV only; no DB needed")

    n = sub.add_parser(
        "import-nutrition",
        help="TFDA 營養資料：--download 下載、--build 產生參考 CSV、預設匯入 DB",
    )
    n.add_argument("--raw", default=str(DEFAULT_RAW_CSV), help="TFDA raw CSV path")
    n.add_argument("--csv", default=str(DEFAULT_NUTRITION_CSV), help="reference CSV path")
    n.add_argument("--report", default=str(DEFAULT_MATCH_REPORT), help="match report path")
    n.add_argument("--seed-csv", default=str(DEFAULT_CSV), help="seed CSV path")
    n.add_argument("--synonyms", default=str(DEFAULT_SYNONYMS_CSV), help="synonym CSV path")
    n.add_argument("--download", action="store_true", help="download raw dataset to data/raw/")
    n.add_argument("--build", action="store_true", help="build reference CSV + match report")
    n.add_argument("--dry-run", action="store_true", help="run in one transaction then roll back")
    n.add_argument("--validate-only", action="store_true", help="validate reference CSV only")
    c = sub.add_parser("crawl-recipes", help="recipe crawl pipeline")
    c.add_argument("--source", default="hakka", choices=["hakka"])
    c.add_argument("--raw", default=None, help="raw JSON path (default data/raw/hakka_recipes.json)")
    c.add_argument("--report", default=None, help="match report path")
    c.add_argument("--download", action="store_true", help="fetch raw file first")
    c.add_argument("--limit", type=int, default=None)
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--validate-only", action="store_true", help="parse+match only; no DB")
    r = sub.add_parser("import-recipes", help="manual recipe CSV import")
    r.add_argument("--recipes", required=True, help="recipes.csv path")
    r.add_argument("--ingredients", required=True, help="recipe_ingredients.csv path")
    r.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "import-seed":
            return _cmd_import_seed(args)
        if args.command == "import-nutrition":
            return _cmd_import_nutrition(args)
        if args.command == "crawl-recipes":
            return _cmd_crawl_recipes(args)
        if args.command == "import-recipes":
            return _cmd_import_recipes(args)
    except (SeedValidationError, NutritionValidationError) as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 1
    return 2


def _cmd_import_recipes(args: argparse.Namespace) -> int:
    import psycopg

    from app.recipe_import import (
        ImportFormatError,
        build_context,
        import_to_db,
        match_recipes,
        parse_import,
    )

    try:
        recipes_bytes = Path(args.recipes).read_bytes()
        ingredients_bytes = Path(args.ingredients).read_bytes()
        result = parse_import(recipes_bytes, ingredients_bytes)
    except (ImportFormatError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for errs in result.recipe_errors.values():
        for e in errs:
            print(f"  reject {e.recipe_id} row{e.row} {e.field}: {e.message}")
    for e in result.errors:
        print(f"  error {e.recipe_id or '-'} row{e.row} {e.field}: {e.message}")
    try:
        database_url = get_database_url()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    with psycopg.connect(database_url) as conn:
        matcher, staples, keyword_map = build_context(conn)
        prepared = match_recipes(result.recipes, matcher, staples, keyword_map)
        if args.dry_run:
            stats = import_to_db(conn, prepared, keyword_map)
            conn.rollback()
        else:
            stats = import_to_db(conn, prepared, keyword_map)
            conn.commit()
    top = sorted(stats.unmatched_names.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    print(
        f"import-recipes{' dry-run: rolled back' if args.dry_run else ''}: "
        f"inserted={stats.inserted} updated={stats.updated} "
        f"unchanged={stats.skipped_unchanged} "
        f"manual-status-skipped={stats.skipped_manual_status} "
        f"rejected={len(result.recipe_errors)} "
        f"unmatched_items={sum(stats.unmatched_names.values())}"
    )
    if top:
        print("  top unmatched: " + "、".join(f"{n}×{c}" for n, c in top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
