import sys
from pathlib import Path

# make `app` importable when running `pytest backend/tests` from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_CSV = REPO_ROOT / "data" / "seed" / "ingredients_draft.csv"
SYNONYMS_CSV = REPO_ROOT / "data" / "reference" / "ingredient_synonyms.csv"
SEED_SQL = REPO_ROOT / "docs" / "db" / "seed_categories_allergens.sql"
SCHEMA_SQL = REPO_ROOT / "docs" / "db" / "schema.sql"
