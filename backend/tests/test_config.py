"""Unit tests for settings parsing, the production guard, helpers and constants."""

import pytest

from app.config import load_settings
from app.repository import like_escape
from app.schemas import ALLOWED_RATINGS_FILTER, RATING_LABELS


def test_settings_defaults():
    s = load_settings({})
    assert s.app_env == "development"
    assert s.include_drafts is False
    assert s.cors_origins == ()
    assert s.database_url == ""


def test_invalid_app_env_raises():
    with pytest.raises(RuntimeError, match="APP_ENV"):
        load_settings({"APP_ENV": "staging"})


def test_production_with_drafts_raises():
    with pytest.raises(RuntimeError, match="INCLUDE_DRAFTS"):
        load_settings({"APP_ENV": "production", "INCLUDE_DRAFTS": "true"})


def test_production_without_drafts_ok():
    s = load_settings({"APP_ENV": "production", "DATABASE_URL": "postgresql://x"})
    assert s.app_env == "production"
    assert s.include_drafts is False


@pytest.mark.parametrize("v", ["true", "1", "yes", "on", "TRUE"])
def test_include_drafts_truthy(v):
    assert load_settings({"INCLUDE_DRAFTS": v}).include_drafts is True


@pytest.mark.parametrize("v", ["", "false", "0", "no", "off"])
def test_include_drafts_falsy(v):
    assert load_settings({"INCLUDE_DRAFTS": v}).include_drafts is False


def test_cors_origins_parsing():
    s = load_settings({"CORS_ORIGINS": " https://a.example ,https://b.example ,,"})
    assert s.cors_origins == ("https://a.example", "https://b.example")


def test_rating_labels_cover_enum():
    assert RATING_LABELS == {
        "suitable": "一般適合",
        "caution": "因人而異",
        "trigger": "常見誘發",
        "unrated": "資料不足",
    }
    assert ALLOWED_RATINGS_FILTER == set(RATING_LABELS)


def test_like_escape():
    assert like_escape("50%_\\") == "50\\%\\_\\\\"
    assert like_escape("雞蛋") == "雞蛋"
