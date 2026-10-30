"""Runtime configuration (environment variables only; no secrets in code)."""

import os
from dataclasses import dataclass, field

VALID_APP_ENVS = {"development", "production", "test"}
MIN_ADMIN_TOKEN_LENGTH = 16
_TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_env: str = "development"
    include_drafts: bool = False
    cors_origins: tuple[str, ...] = field(default_factory=tuple)
    admin_token: str = field(default="", repr=False)


def _parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUE_VALUES


def load_settings(env: dict | None = None) -> Settings:
    """Build Settings from env (default os.environ).

    ADMIN_TOKEN unset/empty disables the admin backend; set but shorter than
    16 characters raises RuntimeError.

    Raises RuntimeError when APP_ENV is invalid, and when
    APP_ENV=production is combined with INCLUDE_DRAFTS=true — drafts must
    never be served by a production deployment.
    """
    env = os.environ if env is None else env
    app_env = env.get("APP_ENV", "development").strip().lower() or "development"
    if app_env not in VALID_APP_ENVS:
        raise RuntimeError(
            f"APP_ENV must be one of {sorted(VALID_APP_ENVS)}, got {app_env!r}"
        )
    include_drafts = _parse_bool(env.get("INCLUDE_DRAFTS"))
    if app_env == "production" and include_drafts:
        raise RuntimeError("INCLUDE_DRAFTS must be false when APP_ENV=production")
    cors_origins = tuple(
        o.strip() for o in env.get("CORS_ORIGINS", "").split(",") if o.strip()
    )
    admin_token = env.get("ADMIN_TOKEN", "").strip()
    if admin_token and len(admin_token) < MIN_ADMIN_TOKEN_LENGTH:
        raise RuntimeError(
            f"ADMIN_TOKEN must be at least {MIN_ADMIN_TOKEN_LENGTH} characters"
        )
    return Settings(
        database_url=env.get("DATABASE_URL", "").strip(),
        app_env=app_env,
        include_drafts=include_drafts,
        cors_origins=cors_origins,
        admin_token=admin_token,
    )


def get_database_url() -> str:
    """Return the PostgreSQL connection string from DATABASE_URL."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url
