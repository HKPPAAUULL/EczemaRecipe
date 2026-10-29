"""Request-scoped helpers shared by the API routers."""

from contextlib import contextmanager

import psycopg
from fastapi import HTTPException, Request


def include_drafts(request: Request) -> bool:
    return request.app.state.settings.include_drafts


@contextmanager
def db_conn(request: Request):
    """Yield a pooled connection; 503 when the pool cannot provide one."""
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    try:
        with pool.connection() as conn:
            yield conn
    except (psycopg.Error, OSError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
