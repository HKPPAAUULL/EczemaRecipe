"""FastAPI application entrypoint."""

import psycopg
from fastapi import FastAPI

from app.db import get_connection

app = FastAPI(title="EczemaRecipe API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Liveness/readiness probe: reports whether the DB answers SELECT 1."""
    db_ok = False
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        db_ok = True
    except (psycopg.Error, OSError, RuntimeError):
        db_ok = False
    return {"status": "ok", "db": db_ok}
