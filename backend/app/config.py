"""Runtime configuration (environment variables only; no secrets in code)."""

import os


def get_database_url() -> str:
    """Return the PostgreSQL connection string from DATABASE_URL."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url
