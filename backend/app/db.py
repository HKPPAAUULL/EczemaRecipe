"""Database connection helper (psycopg 3, plain SQL — no ORM)."""

import psycopg

from app.config import get_database_url


def get_connection(database_url: str | None = None) -> psycopg.Connection:
    """Open a new connection. Caller owns it (use as context manager)."""
    return psycopg.connect(database_url or get_database_url())
