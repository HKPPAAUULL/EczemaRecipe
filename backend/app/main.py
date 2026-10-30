"""FastAPI application entrypoint.

create_app() loads settings once at startup — invalid config (bad APP_ENV or
production + INCLUDE_DRAFTS) raises here so the process fails fast instead of
serving drafts by accident.
"""

from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.api import allergens, categories, ingredients, recipes
from app.config import Settings, load_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    # open lazily: a missing/unreachable DB must not prevent startup —
    # /health reports db:false until it can connect.
    app.state.pool = ConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=5,
        timeout=5,
        kwargs={"row_factory": dict_row},
    )
    yield
    app.state.pool.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="EczemaRecipe API", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET"],
            allow_headers=["*"],
        )

    @app.get("/health")
    def health() -> dict:
        """Liveness/readiness probe: whether the DB answers SELECT 1."""
        db_ok = False
        try:
            with app.state.pool.connection() as conn:
                conn.execute("SELECT 1")
            db_ok = True
        except (psycopg.Error, OSError, RuntimeError):
            db_ok = False
        return {"status": "ok", "db": db_ok}

    app.include_router(ingredients.router)
    app.include_router(categories.router)
    app.include_router(allergens.router)
    app.include_router(recipes.router)
    return app


app = create_app()
