"""Admin authentication: token login, signed session cookie, CSRF, rate limit.

The session cookie is `<expiry>.<nonce>.<hmac>`; the signing key is derived
from ADMIN_TOKEN so rotating the token invalidates every session. The CSRF
token is an HMAC of the session nonce (bound to the session, never stored).
"""

import hashlib
import hmac
import secrets
import time
from collections import deque
from dataclasses import dataclass

from fastapi import HTTPException, Request

COOKIE_NAME = "admin_session"
COOKIE_PATH = "/admin"
SESSION_TTL = 8 * 3600
LOGIN_LIMIT = 5
LOGIN_WINDOW = 60
CLOUDFLARE_HEADERS = ("cf-connecting-ip", "cf-ray")


@dataclass(frozen=True)
class Session:
    nonce: str
    csrf: str


def _key(admin_token: str) -> bytes:
    return hmac.new(admin_token.encode(), b"eczema-admin-session-v1", hashlib.sha256).digest()


def _sign(admin_token: str, payload: str) -> str:
    return hmac.new(_key(admin_token), payload.encode(), hashlib.sha256).hexdigest()


def csrf_for(admin_token: str, nonce: str) -> str:
    return _sign(admin_token, "csrf:" + nonce)


def token_matches(admin_token: str, candidate: str) -> bool:
    return hmac.compare_digest(admin_token.encode(), candidate.encode())


def issue_cookie(admin_token: str, now: float | None = None) -> str:
    expiry = int((time.time() if now is None else now) + SESSION_TTL)
    nonce = secrets.token_hex(16)
    payload = f"{expiry}.{nonce}"
    return f"{payload}.{_sign(admin_token, payload)}"


def parse_cookie(admin_token: str, value: str | None, now: float | None = None) -> Session | None:
    if not value:
        return None
    parts = value.split(".")
    if len(parts) != 3:
        return None
    expiry, nonce, sig = parts
    if not hmac.compare_digest(sig, _sign(admin_token, f"{expiry}.{nonce}")):
        return None
    if not expiry.isdigit() or int(expiry) < (time.time() if now is None else now):
        return None
    return Session(nonce=nonce, csrf=csrf_for(admin_token, nonce))


def verify_csrf(session: Session, supplied: str | None) -> bool:
    return bool(supplied) and hmac.compare_digest(session.csrf, str(supplied))


def is_cloudflare_request(request: Request) -> bool:
    return any(h in request.headers for h in CLOUDFLARE_HEADERS)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class LoginRateLimiter:
    """In-memory: at most LOGIN_LIMIT failed logins per IP per LOGIN_WINDOW seconds."""

    def __init__(self, limit: int = LOGIN_LIMIT, window: int = LOGIN_WINDOW):
        self.limit = limit
        self.window = window
        self._failures: dict[str, deque] = {}

    def _prune(self, ip: str, now: float) -> deque:
        q = self._failures.setdefault(ip, deque())
        while q and now - q[0] >= self.window:
            q.popleft()
        if not q:
            self._failures.pop(ip, None)
        return q

    def blocked(self, ip: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return len(self._prune(ip, now)) >= self.limit

    def record_failure(self, ip: str, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._failures.setdefault(ip, deque()).append(now)

    def reset(self, ip: str) -> None:
        self._failures.pop(ip, None)


def current_session(request: Request) -> Session | None:
    token = request.app.state.settings.admin_token
    return parse_cookie(token, request.cookies.get(COOKIE_NAME))


def require_session(request: Request) -> Session:
    session = current_session(request)
    if session is None:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    return session
