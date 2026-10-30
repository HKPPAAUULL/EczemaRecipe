"""Shared crawl helpers: polite fetch + content hashing + crawl_job records."""

from __future__ import annotations

import hashlib
import time
import urllib.request

USER_AGENT = "EczemaKitchenBot/0.5 (+https://github.com/HKPPAAUULL/EczemaRecipe)"


def fetch_bytes(
    url: str,
    timeout: int = 60,
    retries: int = 3,
    delay: float = 2.0,
    user_agent: str = USER_AGENT,
) -> bytes:
    """GET with User-Agent, timeout, retry and polite delay between attempts."""
    last: Exception | None = None
    for attempt in range(retries):
        if attempt:
            time.sleep(delay * attempt)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": user_agent})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (OSError, ValueError) as exc:  # network/HTTP errors
            last = exc
    raise RuntimeError(f"fetch failed after {retries} attempts: {url}: {last}")


def content_hash(*parts: str) -> str:
    """sha256 of joined parts — incremental-update key for a recipe."""
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:32]


def stable_recipe_slug(name: str) -> str:
    """Deterministic URL-fragment slug for a dish name (source_url UNIQUE)."""
    return "r-" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
