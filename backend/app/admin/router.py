"""Server-rendered admin backend mounted at /admin (only when ADMIN_TOKEN is set).

Cloudflare-tunnelled requests (Cf-Connecting-Ip / Cf-Ray) are refused outright:
the admin UI is for localhost/LAN only.
"""

from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader

from app.admin import auth, rules
from app.admin import repository as repo
from app.deps import db_conn
from app.schemas import RATING_LABELS

STATUS_LABELS = {
    "draft": "草稿",
    "pending_review": "待審核",
    "published": "已發佈",
    "rejected": "已退回",
    "pending": "待處理",
    "approved": "已通過",
}
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}

_env = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=True,
)
_env.globals.update(
    RATING_LABELS=RATING_LABELS,
    STATUS_LABELS=STATUS_LABELS,
    RATINGS=rules.RATINGS,
    SEVERITIES=rules.SEVERITIES,
    PAGE_SIZE=repo.PAGE_SIZE,
)

router = APIRouter(prefix="/admin", include_in_schema=False)


def setup_admin(app: FastAPI) -> None:
    app.state.admin_limiter = auth.LoginRateLimiter()
    app.state.admin_flash = defaultdict(list)

    @app.middleware("http")
    async def admin_guard(request: Request, call_next):
        path = request.url.path
        if path != "/admin" and not path.startswith("/admin/"):
            return await call_next(request)
        if auth.is_cloudflare_request(request):
            response = PlainTextResponse("forbidden", status_code=403)
        else:
            response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.include_router(router)


def render(request: Request, name: str, session: auth.Session | None = None,
           status: int = 200, **ctx) -> HTMLResponse:
    flashes = []
    if session is not None:
        flashes = request.app.state.admin_flash.pop(session.nonce, [])
    html = _env.get_template(name).render(
        csrf=session.csrf if session else "", flashes=flashes, logged_in=session is not None,
        **ctx,
    )
    return HTMLResponse(html, status_code=status)


def flash(request: Request, session: auth.Session, *messages: str) -> None:
    request.app.state.admin_flash[session.nonce].extend(m for m in messages if m)


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


SESSION = Depends(auth.require_session)


async def post_form(request: Request, session: auth.Session = SESSION):
    form = await request.form()
    if not auth.verify_csrf(session, form.get("csrf")):
        raise HTTPException(status_code=403, detail="CSRF token invalid")
    return form


FORM = Depends(post_form)


def _int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _text(form, key: str) -> str:
    return str(form.get(key) or "")


def _page(request: Request) -> int:
    return max(_int(request.query_params.get("page"), 1), 1)


def _pager(total: int, page: int, params: dict) -> dict:
    pages = max((total + repo.PAGE_SIZE - 1) // repo.PAGE_SIZE, 1)
    clean = {k: v for k, v in params.items() if v not in (None, "", False)}
    return {"total": total, "page": page, "pages": pages, "qs": urlencode(clean)}


def _or_404(value):
    if value is None:
        raise HTTPException(status_code=404, detail="not found")
    return value


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if auth.current_session(request):
        return redirect("/admin")
    return render(request, "login.html")


@router.post("/login", response_class=HTMLResponse)
async def login(request: Request):
    settings = request.app.state.settings
    limiter: auth.LoginRateLimiter = request.app.state.admin_limiter
    ip = auth.client_ip(request)
    if limiter.blocked(ip):
        return render(request, "login.html", status=429,
                      error="嘗試次數過多，請一分鐘後再試。")
    form = await request.form()
    if not auth.token_matches(settings.admin_token, _text(form, "token")):
        limiter.record_failure(ip)
        return render(request, "login.html", status=401, error="密碼不正確。")
    limiter.reset(ip)
    response = redirect("/admin")
    response.set_cookie(
        auth.COOKIE_NAME, auth.issue_cookie(settings.admin_token),
        max_age=auth.SESSION_TTL, path=auth.COOKIE_PATH, httponly=True,
        samesite="strict", secure=settings.app_env == "production",
    )
    return response


@router.post("/logout")
def logout(request: Request, session: auth.Session = SESSION,
           form=FORM):
    request.app.state.admin_flash.pop(session.nonce, None)
    response = redirect("/admin/login")
    response.delete_cookie(auth.COOKIE_NAME, path=auth.COOKIE_PATH)
    return response


@router.get("", response_class=HTMLResponse)
def dashboard(request: Request, session: auth.Session = SESSION):
    with db_conn(request) as conn:
        counts = repo.dashboard_counts(conn)
    return render(request, "dashboard.html", session, counts=counts, nav="dashboard")


@router.get("/queue", response_class=HTMLResponse)
def queue(request: Request, session: auth.Session = SESSION):
    page = _page(request)
    with db_conn(request) as conn:
        total, rows = repo.list_queue(conn, page)
    return render(request, "queue.html", session, rows=rows, nav="queue",
                  pager=_pager(total, page, {}))


@router.get("/ingredients", response_class=HTMLResponse)
def ingredients(request: Request, session: auth.Session = SESSION):
    qp = request.query_params
    review = qp.get("review", "unreviewed")
    if review not in repo.INGREDIENT_REVIEW_FILTERS:
        review = "unreviewed"
    rating = qp.get("rating", "")
    category_id = _int(qp.get("category_id"))
    q = qp.get("q", "").strip()
    page = _page(request)
    with db_conn(request) as conn:
        total, rows = repo.list_ingredients(conn, review, rating, category_id, q, page)
        categories = repo.list_categories(conn)
    return render(
        request, "ingredients.html", session, rows=rows, categories=categories,
        nav="ingredients", f={"review": review, "rating": rating,
                              "category_id": category_id, "q": q},
        pager=_pager(total, page, {"review": review, "rating": rating,
                                   "category_id": category_id, "q": q}),
    )


def _ingredient_page(request, session, iid, errors=None, values=None, status=200):
    with db_conn(request) as conn:
        ing = _or_404(repo.get_ingredient_detail(conn, iid))
        categories = repo.list_categories(conn)
        allergens = repo.list_allergens(conn)
    if values is None:
        values = {
            "rating": ing["eczema_rating"], "reason": ing["rating_reason"] or "",
            "senior": ing["needs_senior_review"], "category_id": ing["category_id"],
            "aliases": "\n".join(ing["aliases"]),
        }
    return render(request, "ingredient_detail.html", session, status=status, ing=ing,
                  categories=categories, allergens=allergens, values=values,
                  errors=errors or [], nav="ingredients")


@router.get("/ingredients/{iid}", response_class=HTMLResponse)
def ingredient_detail(iid: int, request: Request,
                      session: auth.Session = SESSION):
    return _ingredient_page(request, session, iid)


def _after_ingredient_change(request, session, iid, errors, reset, ok_message, **page_kwargs):
    if errors:
        return _ingredient_page(request, session, iid, errors=errors, status=422, **page_kwargs)
    flash(request, session, ok_message,
          "此食材已被改動，審核狀態已重置為「未審核」，需重新審核。" if reset else "")
    return redirect(f"/admin/ingredients/{iid}")


@router.post("/ingredients/{iid}/edit")
def ingredient_edit(iid: int, request: Request, session: auth.Session = SESSION, form=FORM):
    values = {
        "rating": _text(form, "rating"), "reason": _text(form, "rating_reason"),
        "senior": form.get("needs_senior_review") == "1",
        "category_id": _int(form.get("category_id")),
        "aliases": _text(form, "aliases"),
    }
    with db_conn(request) as conn:
        errors, reset = repo.save_ingredient(
            conn, iid, values["rating"], values["reason"], values["senior"],
            values["category_id"], rules.parse_aliases(values["aliases"]),
        )
    return _after_ingredient_change(request, session, iid, errors, reset, "已儲存食材。",
                                    values=values)


@router.post("/ingredients/{iid}/allergens/add")
def allergen_add(iid: int, request: Request,
                 session: auth.Session = SESSION,
                 form=FORM):
    with db_conn(request) as conn:
        errors, reset = repo.add_allergen(
            conn, iid, _int(form.get("allergen_id"), -1), _text(form, "severity") or None)
    return _after_ingredient_change(request, session, iid, errors, reset, "已儲存過敏原連結。")


@router.post("/ingredients/{iid}/allergens/{allergen_id}/delete")
def allergen_delete(iid: int, allergen_id: int, request: Request,
                    session: auth.Session = SESSION,
                    form=FORM):
    with db_conn(request) as conn:
        errors, reset = repo.delete_allergen(conn, iid, allergen_id)
    return _after_ingredient_change(request, session, iid, errors, reset, "已刪除過敏原連結。")


@router.post("/ingredients/{iid}/evidence/add")
def evidence_add(iid: int, request: Request,
                 session: auth.Session = SESSION,
                 form=FORM):
    with db_conn(request) as conn:
        errors, reset = repo.add_evidence(
            conn, iid, _text(form, "title"), _text(form, "url"),
            _text(form, "source_type"), _text(form, "year"))
    return _after_ingredient_change(request, session, iid, errors, reset, "已新增證據。")


@router.post("/ingredients/{iid}/evidence/{evidence_id}/delete")
def evidence_delete(iid: int, evidence_id: int, request: Request,
                    session: auth.Session = SESSION,
                    form=FORM):
    with db_conn(request) as conn:
        errors, reset = repo.delete_evidence(conn, iid, evidence_id)
    return _after_ingredient_change(request, session, iid, errors, reset, "已刪除證據。")


@router.post("/ingredients/{iid}/review")
def ingredient_review(iid: int, request: Request,
                      session: auth.Session = SESSION,
                      form=FORM):
    with db_conn(request) as conn:
        errors = repo.set_ingredient_reviewed(conn, iid, True)
    return _after_ingredient_change(request, session, iid, errors, False, "已標記為已審核，現已公開。")


@router.post("/ingredients/{iid}/unreview")
def ingredient_unreview(iid: int, request: Request,
                        session: auth.Session = SESSION,
                        form=FORM):
    with db_conn(request) as conn:
        errors = repo.set_ingredient_reviewed(conn, iid, False)
    return _after_ingredient_change(request, session, iid, errors, False, "已取消審核，現已不公開。")


@router.get("/recipes", response_class=HTMLResponse)
def recipes(request: Request, session: auth.Session = SESSION):
    qp = request.query_params
    status = qp.get("status", "")
    unmatched = qp.get("unmatched") == "1"
    q = qp.get("q", "").strip()
    page = _page(request)
    with db_conn(request) as conn:
        total, rows = repo.list_recipes(conn, status, unmatched, q, page)
    params = {"status": status, "unmatched": "1" if unmatched else "", "q": q}
    return render(request, "recipes.html", session, rows=rows, nav="recipes",
                  f={"status": status, "unmatched": unmatched, "q": q},
                  statuses=repo.RECIPE_STATUSES, pager=_pager(total, page, params))


def _recipe_page(request, session, rid, errors=None, status=200, form=None):
    qp = request.query_params
    find = qp.get("find", "")
    q = qp.get("q", find).strip() if find else ""
    with db_conn(request) as conn:
        rec = _or_404(repo.get_recipe_detail(conn, rid))
        candidates = repo.search_ingredients(conn, q) if find else []
    score = rec["eczema_friendly_score"]
    values = {
        "description": rec["description"] or "",
        "score": "" if score is None else f"{score:g}",
        "cook_time": "" if rec["cook_time"] is None else rec["cook_time"],
        "servings": "" if rec["servings"] is None else rec["servings"],
    }
    if form is not None:
        values = {"description": _text(form, "description"), "score": _text(form, "score"),
                  "cook_time": _text(form, "cook_time"), "servings": _text(form, "servings")}
    return render(request, "recipe_detail.html", session, status=status, rec=rec,
                  values=values, find=find, q=q, candidates=candidates,
                  errors=errors or [], nav="recipes")


@router.get("/recipes/{rid}", response_class=HTMLResponse)
def recipe_detail(rid: int, request: Request,
                  session: auth.Session = SESSION):
    return _recipe_page(request, session, rid)


def _after_recipe_change(request, session, rid, errors, ok_message, form=None):
    if errors:
        return _recipe_page(request, session, rid, errors=errors, status=422, form=form)
    flash(request, session, ok_message)
    return redirect(f"/admin/recipes/{rid}")


@router.post("/recipes/{rid}/edit")
def recipe_edit(rid: int, request: Request,
                session: auth.Session = SESSION,
                form=FORM):
    with db_conn(request) as conn:
        errors = repo.edit_recipe(
            conn, rid, _text(form, "description"), _text(form, "score"),
            _text(form, "cook_time"), _text(form, "servings"))
    return _after_recipe_change(request, session, rid, errors, "已儲存食譜資料。", form)


@router.post("/recipes/{rid}/unmatched/map")
def recipe_map(rid: int, request: Request,
               session: auth.Session = SESSION,
               form=FORM):
    with db_conn(request) as conn:
        errors = repo.map_unmatched(
            conn, rid, _text(form, "item"), _int(form.get("ingredient_id"), -1),
            form.get("is_staple") == "1")
    return _after_recipe_change(request, session, rid, errors, "已配對食材。")


@router.post("/recipes/{rid}/unmatched/ignore")
def recipe_ignore(rid: int, request: Request,
                  session: auth.Session = SESSION,
                  form=FORM):
    with db_conn(request) as conn:
        errors = repo.ignore_unmatched(conn, rid, _text(form, "item"), _text(form, "reason"))
    return _after_recipe_change(request, session, rid, errors, "已忽略該項目。")


@router.post("/recipes/{rid}/unmatched/staple")
def recipe_staple(rid: int, request: Request,
                  session: auth.Session = SESSION,
                  form=FORM):
    with db_conn(request) as conn:
        errors = repo.staple_unmatched(conn, rid, _text(form, "item"))
    return _after_recipe_change(request, session, rid, errors, "已移到未配對調味料。")


@router.post("/recipes/{rid}/status")
def recipe_status(rid: int, request: Request,
                  session: auth.Session = SESSION,
                  form=FORM):
    action = _text(form, "action")
    with db_conn(request) as conn:
        errors = repo.change_recipe_status(conn, rid, action, _text(form, "reason"))
    label = rules.ACTION_LABELS.get(action, "")
    return _after_recipe_change(request, session, rid, errors, f"已執行「{label}」。")
