"""Command-line entry: ``python -m app.cli import-seed [--csv PATH] [--dry-run]``.

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("import-seed", help="import data/seed/ingredients_draft.csv into the DB")
    p.add_argument("--csv", default=str(DEFAULT_CSV), help="path to the seed CSV")
    p.add_argument("--synonyms", default=str(DEFAULT_SYNONYMS_CSV), help="synonym CSV path")
    p.add_argument("--seed-sql", default=str(DEFAULT_SEED_SQL), help="seed SQL file (category check)")
    p.add_argument("--dry-run", action="store_true", help="run in one transaction then roll back")
    p.add_argument("--validate-only", action="store_true", help="validate CSV only; no DB needed")
    args = parser.parse_args(argv)

    try:
        if args.command == "import-seed":
            return _cmd_import_seed(args)
    except SeedValidationError as exc:
        print(f"validation error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
