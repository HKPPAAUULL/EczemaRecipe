"""Auth / CSRF / header tests for /admin (no real DB needed)."""

import os

import pytest
from app.admin import auth
from app.config import Settings, load_settings
from app.main import create_app
from fastapi.testclient import TestClient

TOKEN = "unit-test-admin-token-123456"
DB = os.environ.get("TEST_DATABASE_URL") or "postgresql://nobody@127.0.0.1:1/none"


def make_client(token=TOKEN, env="test"):
    app = create_app(Settings(database_url=DB, app_env=env, admin_token=token))
    return TestClient(app, follow_redirects=False)


@pytest.fixture(scope="module")
def _shared_client():
    with make_client() as c:
        yield c


@pytest.fixture()
def client(_shared_client):
    _shared_client.cookies.clear()
    _shared_client.app.state.admin_limiter = auth.LoginRateLimiter()
    return _shared_client


def login(client, token=TOKEN):
    return client.post("/admin/login", data={"token": token})


def csrf(client):
    return auth.parse_cookie(TOKEN, client.cookies.get(auth.COOKIE_NAME)).csrf


def test_admin_disabled_without_token():
    with make_client(token="") as c:
        for path in ("/admin", "/admin/login", "/admin/ingredients"):
            assert c.get(path).status_code == 404
        assert c.post("/admin/login", data={"token": "x"}).status_code == 404


def test_short_token_fails_startup():
    with pytest.raises(RuntimeError, match="ADMIN_TOKEN"):
        load_settings({"ADMIN_TOKEN": "short"})
    assert load_settings({"ADMIN_TOKEN": "x" * 16}).admin_token == "x" * 16
    assert load_settings({}).admin_token == ""
    assert load_settings({"APP_ENV": "production", "ADMIN_TOKEN": "x" * 16}).admin_token


def test_token_not_in_repr():
    assert TOKEN not in repr(Settings(database_url=DB, admin_token=TOKEN))


@pytest.mark.parametrize("path", [
    "/admin", "/admin/ingredients", "/admin/ingredients/1", "/admin/recipes",
    "/admin/recipes/1", "/admin/queue"])
def test_unauthenticated_redirects_to_login(client, path):
    r = client.get(path)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


@pytest.mark.parametrize("path", [
    "/admin/logout", "/admin/ingredients/1/edit", "/admin/ingredients/1/review",
    "/admin/recipes/1/status", "/admin/recipes/1/unmatched/map"])
def test_unauthenticated_post_redirects(client, path):
    r = client.post(path, data={"csrf": "x"})
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


def test_login_page_ok(client):
    r = client.get("/admin/login")
    assert r.status_code == 200
    assert "ADMIN_TOKEN" in r.text and TOKEN not in r.text


def test_wrong_token_rejected(client):
    r = login(client, "wrong")
    assert r.status_code == 401
    assert auth.COOKIE_NAME not in r.headers.get("set-cookie", "")
    assert TOKEN not in r.text


def test_login_sets_hardened_cookie(client):
    r = login(client)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin"
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/admin" in cookie
    assert "max-age=28800" in cookie
    assert "secure" not in cookie
    assert TOKEN not in r.headers["set-cookie"]


def test_cookie_secure_in_production():
    with make_client(env="production") as c:
        r = login(c)
        assert "secure" in r.headers["set-cookie"].lower()


def test_rate_limit_after_five_failures(client):
    for _ in range(5):
        assert login(client, "bad").status_code == 401
    assert login(client, "bad").status_code == 429
    assert login(client).status_code == 429


def test_rate_limit_unit():
    lim = auth.LoginRateLimiter(limit=2, window=60)
    assert not lim.blocked("ip", now=0)
    lim.record_failure("ip", now=0)
    lim.record_failure("ip", now=1)
    assert lim.blocked("ip", now=2)
    assert not lim.blocked("other", now=2)
    assert not lim.blocked("ip", now=61.5)
    lim.record_failure("ip", now=70)
    lim.reset("ip")
    assert not lim.blocked("ip", now=71)


def test_csrf_required_on_post(client):
    login(client)
    assert client.post("/admin/logout").status_code == 403
    assert client.post("/admin/logout", data={"csrf": "nope"}).status_code == 403
    assert client.post("/admin/ingredients/1/review", data={}).status_code == 403
    assert client.post("/admin/recipes/1/status", data={"action": "publish"}).status_code == 403


def test_csrf_token_bound_to_session():
    a, b = auth.issue_cookie(TOKEN), auth.issue_cookie(TOKEN)
    sa, sb = auth.parse_cookie(TOKEN, a), auth.parse_cookie(TOKEN, b)
    assert sa.csrf != sb.csrf
    assert not auth.verify_csrf(sa, sb.csrf)
    assert auth.verify_csrf(sa, sa.csrf)
    assert not auth.verify_csrf(sa, None)
    assert not auth.verify_csrf(sa, "")


def test_logout_clears_cookie(client):
    login(client)
    r = client.post("/admin/logout", data={"csrf": csrf(client)})
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"
    assert "max-age=0" in r.headers["set-cookie"].lower()
    assert client.get("/admin").status_code == 303


def test_tampered_cookie_rejected(client):
    value = auth.issue_cookie(TOKEN)
    expiry, nonce, sig = value.split(".")
    for bad in (f"{expiry}.{nonce}.{'0' * len(sig)}", f"{int(expiry) + 99999}.{nonce}.{sig}",
                f"{expiry}.other.{sig}", "garbage", f"{expiry}.{nonce}", ""):
        client.cookies.clear()
        client.cookies.set(auth.COOKIE_NAME, bad, path="/admin")
        assert client.get("/admin").status_code == 303, bad


def test_expired_and_foreign_cookie_rejected(client):
    for value in (auth.issue_cookie(TOKEN, now=0), auth.issue_cookie("another-token-1234567890")):
        client.cookies.clear()
        client.cookies.set(auth.COOKIE_NAME, value, path="/admin")
        assert client.get("/admin").status_code == 303


def test_cloudflare_headers_forbidden(client):
    login(client)
    for hdr in ({"Cf-Connecting-Ip": "1.2.3.4"}, {"Cf-Ray": "abc-HKG"}):
        for path in ("/admin", "/admin/login", "/admin/ingredients"):
            assert client.get(path, headers=hdr).status_code == 403
        assert client.post("/admin/login", data={"token": TOKEN}, headers=hdr).status_code == 403
    assert client.get("/health", headers={"Cf-Ray": "x"}).status_code == 200


def test_security_headers(client):
    login(client)
    responses = [
        client.get("/admin/login"), client.get("/admin"),
        client.post("/admin/login", data={"token": "bad"}),
        client.get("/admin/login", headers={"Cf-Ray": "x"}),
    ]
    for r in responses:
        assert r.headers["cache-control"] == "no-store"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer"


def test_admin_not_in_openapi(client):
    assert "/admin" not in str(client.get("/openapi.json").json()["paths"])
