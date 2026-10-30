"""Admin backend integration tests — need TEST_DATABASE_URL (use a scratch DB)."""

import os

import pytest
from conftest import REPO_ROOT, SCHEMA_SQL, SEED_SQL
from fastapi.testclient import TestClient

from app.admin import auth
from app.config import Settings
from app.main import create_app

psycopg = pytest.importorskip("psycopg")
TEST_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="TEST_DATABASE_URL not set — integration tests skipped"
)
TOKEN = "integration-admin-token-123456"


@pytest.fixture()
def db():
    with psycopg.connect(TEST_URL, autocommit=True) as conn:
        if conn.execute("SELECT to_regclass('public.ingredient')").fetchone()[0] is None:
            conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
            conn.execute(SEED_SQL.read_text(encoding="utf-8"))
        conn.execute(
            (REPO_ROOT / "docs/db/migrations/0005_audit_log.sql").read_text(encoding="utf-8")
            if conn.execute("SELECT to_regclass('public.audit_log')").fetchone()[0] is None
            else "SELECT 1"
        )
        conn.execute(
            "TRUNCATE evidence, ingredient_allergen, ingredient_nutrient, recipe_tag,"
            " recipe_ingredient, recipe, ingredient, review_queue, audit_log"
            " RESTART IDENTITY CASCADE"
        )
        conn.execute(
            "CREATE OR REPLACE VIEW published_recipe AS SELECT * FROM recipe "
            "WHERE status = 'published' AND cardinality(unmatched_ingredients) = 0"
        )
        yield conn


@pytest.fixture()
def client(db):
    app = create_app(Settings(database_url=TEST_URL, app_env="test", admin_token=TOKEN))
    with TestClient(app, follow_redirects=False) as c:
        assert c.post("/admin/login", data={"token": TOKEN}).status_code == 303
        yield c


@pytest.fixture()
def public(db):
    app = create_app(Settings(database_url=TEST_URL, app_env="test"))
    with TestClient(app) as c:
        yield c


def post(client, path, **data):
    token = auth.parse_cookie(TOKEN, client.cookies.get(auth.COOKIE_NAME)).csrf
    return client.post(path, data={"csrf": token, **data})


def mk_ing(db, name, rating="suitable", reason=None, reviewed=False, allergen=None):
    iid = db.execute(
        "INSERT INTO ingredient (name_zh, eczema_rating, rating_reason, reviewed)"
        " VALUES (%s, %s, %s, %s) RETURNING id", (name, rating, reason, reviewed)
    ).fetchone()[0]
    if allergen:
        db.execute(
            "INSERT INTO ingredient_allergen (ingredient_id, allergen_id)"
            " SELECT %s, id FROM allergen WHERE type = %s LIMIT 1", (iid, allergen))
    return iid


def mk_recipe(db, title="測試食譜", status="pending_review", unmatched=(), matched=(),
              hints=()):
    rid = db.execute(
        "INSERT INTO recipe (title, status, unmatched_ingredients, allergen_hints)"
        " VALUES (%s, %s, %s, %s) RETURNING id", (title, status, list(unmatched), list(hints))
    ).fetchone()[0]
    for iid in matched:
        db.execute(
            "INSERT INTO recipe_ingredient (recipe_id, ingredient_id, raw_text)"
            " VALUES (%s, %s, 'x')", (rid, iid))
    db.execute(
        "INSERT INTO review_queue (entity_type, entity_id, reviewer_note)"
        " VALUES ('recipe', %s, 'crawler')", (rid,))
    return rid


def one(db, sql, *args):
    return db.execute(sql, args).fetchone()[0]


def public_ids(public, q):
    return [i["id"] for i in public.get("/api/ingredients/search", params={"q": q}).json()["items"]]


def edit(client, iid, rating, reason="", **extra):
    return post(client, f"/admin/ingredients/{iid}/edit", rating=rating,
                rating_reason=reason, **extra)


def audit_actions(db, etype, eid):
    return [r[0] for r in db.execute(
        "SELECT action FROM audit_log WHERE entity_type=%s AND entity_id=%s ORDER BY id",
        (etype, eid)).fetchall()]


def test_ingredient_review_flow_and_public_api(db, client, public):
    iid = mk_ing(db, "測試蘋果", "suitable")
    assert iid not in public_ids(public, "測試蘋果")
    assert public.get(f"/api/ingredients/{iid}").status_code == 404

    r = post(client, f"/admin/ingredients/{iid}/review")
    assert r.status_code == 303
    assert one(db, "SELECT reviewed FROM ingredient WHERE id=%s", iid) is True
    assert one(db, "SELECT reviewed_at IS NOT NULL FROM ingredient WHERE id=%s", iid)
    assert iid in public_ids(public, "測試蘋果")
    assert public.get(f"/api/ingredients/{iid}").status_code == 200

    assert post(client, f"/admin/ingredients/{iid}/unreview").status_code == 303
    assert iid not in public_ids(public, "測試蘋果")
    assert one(db, "SELECT reviewed_at IS NULL FROM ingredient WHERE id=%s", iid)
    assert audit_actions(db, "ingredient", iid) == ["review", "unreview"]


def test_edit_validation_rejects_and_keeps_data(db, client):
    iid = mk_ing(db, "規則食材", "unrated")
    r = edit(client, iid, "caution", "")
    assert r.status_code == 422 and "必須填寫評級原因" in r.text
    assert edit(client, iid, "caution", "可以根治濕疹").status_code == 422
    assert edit(client, iid, "bogus", "x").status_code == 422
    assert one(db, "SELECT eczema_rating::text FROM ingredient WHERE id=%s", iid) == "unrated"
    assert audit_actions(db, "ingredient", iid) == []
    assert edit(client, iid, "caution", "常見過敏原之一").status_code == 303
    assert one(db, "SELECT eczema_rating::text FROM ingredient WHERE id=%s", iid) == "caution"


def test_trigger_needs_http_evidence_to_review(db, client):
    iid = mk_ing(db, "誘發食材", "trigger", "有權威指引")
    r = post(client, f"/admin/ingredients/{iid}/review")
    assert r.status_code == 422 and "證據" in r.text
    assert one(db, "SELECT reviewed FROM ingredient WHERE id=%s", iid) is False
    bad = post(client, f"/admin/ingredients/{iid}/evidence/add", title="t",
               url="javascript:alert(1)")
    assert bad.status_code == 422
    assert one(db, "SELECT count(*) FROM evidence WHERE ingredient_id=%s", iid) == 0
    ok = post(client, f"/admin/ingredients/{iid}/evidence/add", title="指引",
              url="https://example.org/g", source_type="guideline", year="2022")
    assert ok.status_code == 303
    dup = post(client, f"/admin/ingredients/{iid}/evidence/add", title="指引2",
               url="https://example.org/g")
    assert dup.status_code == 422 and "相同網址" in dup.text
    assert post(client, f"/admin/ingredients/{iid}/review").status_code == 303
    assert one(db, "SELECT reviewed FROM ingredient WHERE id=%s", iid) is True


def test_major_allergen_cannot_be_reviewed_suitable(db, client):
    iid = mk_ing(db, "含過敏原", "suitable", allergen="major_allergen")
    r = post(client, f"/admin/ingredients/{iid}/review")
    assert r.status_code == 422 and "九大過敏原" in r.text
    assert one(db, "SELECT reviewed FROM ingredient WHERE id=%s", iid) is False
    assert edit(client, iid, "caution", "為常見食物過敏原之一").status_code == 303
    assert post(client, f"/admin/ingredients/{iid}/review").status_code == 303


def test_editing_reviewed_ingredient_resets_review(db, client, public):
    iid = mk_ing(db, "已審核食材", "caution", "原因甲", reviewed=True)
    db.execute("UPDATE ingredient SET reviewed_at = now() WHERE id=%s", (iid,))
    assert iid in public_ids(public, "已審核食材")

    r = edit(client, iid, "caution", "原因甲", needs_senior_review="1", aliases="別名甲")
    assert r.status_code == 303
    assert one(db, "SELECT reviewed FROM ingredient WHERE id=%s", iid) is True

    assert edit(client, iid, "caution", "原因乙").status_code == 303
    assert one(db, "SELECT reviewed FROM ingredient WHERE id=%s", iid) is False
    assert iid not in public_ids(public, "已審核食材")
    assert "auto_unreview" in audit_actions(db, "ingredient", iid)
    page = client.get(f"/admin/ingredients/{iid}")
    assert page.status_code == 200 and "未審核" in page.text


@pytest.mark.parametrize("change", ["allergen_add", "allergen_del", "evidence_add", "evidence_del"])
def test_related_changes_reset_review(db, client, change):
    iid = mk_ing(db, "關聯食材", "caution", "原因", reviewed=True)
    aid = one(db, "SELECT id FROM allergen WHERE type='major_allergen' LIMIT 1")
    db.execute("INSERT INTO ingredient_allergen (ingredient_id, allergen_id) VALUES (%s,%s)",
               (iid, aid))
    db.execute("INSERT INTO evidence (ingredient_id, title, url) VALUES (%s,'e','https://a.org')",
               (iid,))
    eid = one(db, "SELECT id FROM evidence WHERE ingredient_id=%s", iid)
    other = one(db, "SELECT id FROM allergen WHERE id <> %s ORDER BY id LIMIT 1", aid)
    path = {
        "allergen_add": (f"/admin/ingredients/{iid}/allergens/add", {"allergen_id": other, "severity": "high"}),
        "allergen_del": (f"/admin/ingredients/{iid}/allergens/{aid}/delete", {}),
        "evidence_add": (f"/admin/ingredients/{iid}/evidence/add", {"title": "n", "url": "https://b.org"}),
        "evidence_del": (f"/admin/ingredients/{iid}/evidence/{eid}/delete", {}),
    }[change]
    assert post(client, path[0], **path[1]).status_code == 303
    assert one(db, "SELECT reviewed FROM ingredient WHERE id=%s", iid) is False


def test_list_filters_and_pages_render(db, client):
    a = mk_ing(db, "篩選甲<script>", "unrated")
    b = mk_ing(db, "篩選乙", "caution", "r", reviewed=True)
    db.execute("UPDATE ingredient SET needs_senior_review = true WHERE id=%s", (a,))
    body = client.get("/admin/ingredients").text
    assert "<script>" not in body and "&lt;script&gt;" in body
    assert "篩選乙" not in body
    assert "篩選乙" in client.get("/admin/ingredients?review=reviewed").text
    assert "篩選甲" in client.get("/admin/ingredients?review=senior").text
    assert "篩選甲" in client.get("/admin/ingredients?review=unrated").text
    assert "篩選乙" in client.get("/admin/ingredients?review=all&rating=caution&q=篩選").text
    assert "篩選甲" not in client.get("/admin/ingredients?review=all&rating=caution").text
    assert client.get(f"/admin/ingredients/{b}").status_code == 200
    assert client.get("/admin/ingredients/99999").status_code == 404
    assert client.get("/admin/ingredients?page=abc&category_id=x").status_code == 200
    dash = client.get("/admin").text
    assert TOKEN not in dash and client.get("/admin/queue").status_code == 200


def test_unmatched_map_ignore_staple_and_publish(db, client, public):
    pork = mk_ing(db, "測試豬肉", "suitable", reviewed=True)
    coriander = mk_ing(db, "測試芫荽", "suitable")
    rid = mk_recipe(db, unmatched=["香菜少許", "芫荽1棵", "請參考圖片", "高湯1碗"],
                    matched=[pork], hints=["蛋"])

    r = post(client, f"/admin/recipes/{rid}/status", action="publish")
    assert r.status_code == 422 and "未配對" in r.text
    assert one(db, "SELECT status::text FROM recipe WHERE id=%s", rid) == "pending_review"

    find = client.get(f"/admin/recipes/{rid}", params={"find": "香菜少許", "q": "芫荽"})
    assert find.status_code == 200 and "測試芫荽" in find.text

    assert post(client, f"/admin/recipes/{rid}/unmatched/map", item="香菜少許",
                ingredient_id=coriander).status_code == 303
    assert post(client, f"/admin/recipes/{rid}/unmatched/map", item="芫荽1棵",
                ingredient_id=coriander, is_staple="1").status_code == 303
    row = db.execute("SELECT raw_text, is_staple, qty, unit FROM recipe_ingredient"
                     " WHERE recipe_id=%s AND ingredient_id=%s", (rid, coriander)).fetchone()
    assert row == ("香菜少許；芫荽1棵", False, None, None)

    again = post(client, f"/admin/recipes/{rid}/unmatched/map", item="香菜少許",
                 ingredient_id=coriander)
    assert again.status_code == 422 and "已被處理" in again.text

    no_reason = post(client, f"/admin/recipes/{rid}/unmatched/ignore", item="請參考圖片", reason=" ")
    assert no_reason.status_code == 422
    assert post(client, f"/admin/recipes/{rid}/unmatched/ignore", item="請參考圖片",
                reason="非食材").status_code == 303
    assert post(client, f"/admin/recipes/{rid}/unmatched/staple", item="高湯1碗").status_code == 303
    rec = db.execute("SELECT unmatched_ingredients, unmatched_staples, allergen_hints"
                     " FROM recipe WHERE id=%s", (rid,)).fetchone()
    assert rec == ([], ["高湯1碗"], ["蛋"])
    note = one(db, "SELECT reviewer_note FROM review_queue WHERE entity_id=%s", rid)
    assert "crawler" in note and "非食材" in note and "請參考圖片" in note

    blocked = post(client, f"/admin/recipes/{rid}/status", action="publish")
    assert blocked.status_code == 422 and "測試芫荽" in blocked.text
    assert one(db, "SELECT count(*) FROM published_recipe WHERE id=%s", rid) == 0
    assert public.get(f"/api/recipes/{rid}").status_code == 404

    assert post(client, f"/admin/ingredients/{coriander}/review").status_code == 303
    assert post(client, f"/admin/recipes/{rid}/status", action="publish").status_code == 303
    assert one(db, "SELECT count(*) FROM published_recipe WHERE id=%s", rid) == 1
    assert public.get(f"/api/recipes/{rid}").status_code == 200
    q = db.execute("SELECT status::text, reviewer_note FROM review_queue WHERE entity_id=%s",
                   (rid,)).fetchone()
    assert q[0] == "approved" and "發佈" in q[1]
    actions = audit_actions(db, "recipe", rid)
    assert actions == ["map_unmatched", "map_unmatched", "ignore_unmatched",
                       "staple_unmatched", "publish"]
    assert one(db, "SELECT allergen_hints FROM recipe WHERE id=%s", rid) == ["蛋"]


def test_publish_requires_non_staple_and_reviewed(db, client):
    ing = mk_ing(db, "調味料食材", "suitable", reviewed=True)
    rid = mk_recipe(db, matched=[])
    r = post(client, f"/admin/recipes/{rid}/status", action="publish")
    assert r.status_code == 422 and "非調味料" in r.text
    db.execute("INSERT INTO recipe_ingredient (recipe_id, ingredient_id, raw_text, is_staple)"
               " VALUES (%s,%s,'鹽',true)", (rid, ing))
    assert post(client, f"/admin/recipes/{rid}/status", action="publish").status_code == 422
    db.execute("UPDATE recipe_ingredient SET is_staple=false WHERE recipe_id=%s", (rid,))
    db.execute("UPDATE ingredient SET reviewed=false WHERE id=%s", (ing,))
    assert "尚未審核" in post(client, f"/admin/recipes/{rid}/status", action="publish").text
    db.execute("UPDATE ingredient SET reviewed=true WHERE id=%s", (ing,))
    assert post(client, f"/admin/recipes/{rid}/status", action="publish").status_code == 303


def test_reject_resubmit_and_queue(db, client):
    rid = mk_recipe(db, unmatched=["x"])
    assert post(client, f"/admin/recipes/{rid}/status", action="reject").status_code == 422
    assert post(client, f"/admin/recipes/{rid}/status", action="reject",
                reason="來源不明").status_code == 303
    assert one(db, "SELECT status::text FROM recipe WHERE id=%s", rid) == "rejected"
    row = db.execute("SELECT status::text, reviewer_note FROM review_queue WHERE entity_id=%s",
                     (rid,)).fetchone()
    assert row[0] == "rejected" and "來源不明" in row[1]
    assert f'href="/admin/recipes/{rid}"' not in client.get("/admin/queue").text
    assert post(client, f"/admin/recipes/{rid}/status", action="publish").status_code == 422
    assert post(client, f"/admin/recipes/{rid}/status", action="resubmit").status_code == 303
    assert one(db, "SELECT status::text FROM recipe WHERE id=%s", rid) == "pending_review"
    assert one(db, "SELECT count(*) FROM review_queue WHERE entity_id=%s AND status='pending'",
               rid) == 1
    assert f'href="/admin/recipes/{rid}"' in client.get("/admin/queue").text


def test_recipe_edit_and_validation(db, client):
    rid = mk_recipe(db)
    ok = post(client, f"/admin/recipes/{rid}/edit", description="簡介", score="88.5",
              cook_time="30", servings="2")
    assert ok.status_code == 303
    row = db.execute("SELECT description, eczema_friendly_score, cook_time, servings"
                     " FROM recipe WHERE id=%s", (rid,)).fetchone()
    assert (row[0], float(row[1]), row[2], row[3]) == ("簡介", 88.5, 30, 2)
    for bad in ({"score": "101"}, {"cook_time": "-1"}, {"servings": "0"}):
        data = {"description": "x", "score": "", "cook_time": "", "servings": "", **bad}
        assert post(client, f"/admin/recipes/{rid}/edit", **data).status_code == 422
    cleared = post(client, f"/admin/recipes/{rid}/edit", description="", score="")
    assert cleared.status_code == 303
    assert one(db, "SELECT eczema_friendly_score FROM recipe WHERE id=%s", rid) is None
    assert audit_actions(db, "recipe", rid) == ["edit", "edit"]


def test_recipe_pages_render_and_filter(db, client):
    ing = mk_ing(db, "頁面食材", "caution", "r", reviewed=True, allergen="major_allergen")
    rid = mk_recipe(db, "頁面<b>食譜", unmatched=["怪食材"], matched=[ing], hints=["蛋"])
    mk_recipe(db, "乾淨食譜", status="draft")
    page = client.get(f"/admin/recipes/{rid}")
    assert page.status_code == 200
    assert "<b>食譜" not in page.text and "&lt;b&gt;食譜" in page.text
    assert "怪食材" in page.text and "頁面食材" in page.text and TOKEN not in page.text
    assert "乾淨食譜" not in client.get("/admin/recipes?unmatched=1").text
    assert "乾淨食譜" in client.get("/admin/recipes?status=draft").text
    assert client.get("/admin/recipes/99999").status_code == 404
    assert post(client, "/admin/recipes/99999/status", action="publish").status_code == 404


# --------------------------------------------------------------------------
# Recipe authoring (v0.9.0): form, CSV import, exports
# --------------------------------------------------------------------------

def _mk(db, name, reviewed=True, **kw):
    return mk_ing(db, name, reviewed=reviewed, **kw)


def test_recipe_new_form_creates_draft(db, client):
    _mk(db, "雞蛋"); _mk(db, "鹽")
    r = post(client, "/admin/recipes/new",
             title="蒸蛋", description="", cook_time="15", servings="2",
             steps="打散\n蒸熟", tags="蒸", notes="",
             ing_name=["雞蛋", "鹽"], ing_qty=["2", ""], ing_unit=["顆", ""],
             ing_note=["", ""], ing_staple=["1"])
    assert r.status_code == 303
    rid = one(db, "SELECT id FROM recipe WHERE is_original")
    rec = db.execute(
        "SELECT status, steps, allergen_hints FROM recipe WHERE id=%s",
        (rid,)).fetchone()
    assert rec[0] == "draft" and rec[1] == ["打散", "蒸熟"]
    assert one(db, "SELECT count(*) FROM recipe_ingredient WHERE recipe_id=%s",
               rid) == 2
    assert "蛋" in list(rec[2])  # 雞蛋 keyword


def test_recipe_new_forbidden_and_min_items(db, client):
    _mk(db, "雞蛋"); _mk(db, "鹽")
    r = post(client, "/admin/recipes/new",
             title="抗濕疹食譜", description="", cook_time="", servings="",
             steps="a", tags="", notes="",
             ing_name=["雞蛋", "鹽"], ing_qty=["", ""], ing_unit=["", ""],
             ing_note=["", ""], ing_staple=[])
    assert r.status_code == 422 and "禁用詞" in r.text
    r = post(client, "/admin/recipes/new",
             title="ok", description="", cook_time="", servings="",
             steps="a", tags="", notes="",
             ing_name=["雞蛋"], ing_qty=[""], ing_unit=[""], ing_note=[""],
             ing_staple=[])
    assert r.status_code == 422


def test_content_edit_recomputes_and_demotes(db, client):
    _mk(db, "雞蛋"); _mk(db, "鹽")
    rid = one(db, "SELECT id FROM recipe WHERE is_original") \
        if one(db, "SELECT count(*) FROM recipe WHERE is_original") else None
    if rid is None:
        rid = mk_recipe(db, title="原創", status="published")
        db.execute("UPDATE recipe SET is_original=true WHERE id=%s", (rid,))
    iid = db.execute("SELECT id FROM ingredient WHERE name_zh='雞蛋'").fetchone()[0]
    db.execute("INSERT INTO recipe_ingredient (recipe_id, ingredient_id, raw_text)"
               " VALUES (%s,%s,'x') ON CONFLICT DO NOTHING", (rid, iid))
    r = post(client, f"/admin/recipes/{rid}/content",
             title="原創改", description="", cook_time="5", servings="1",
             steps="a", tags="", notes="",
             ing_name=["雞蛋", "鹽"], ing_qty=["1", ""], ing_unit=["顆", ""],
             ing_note=["", ""], ing_staple=["1"])
    assert r.status_code == 303
    rec = db.execute("SELECT status, allergen_hints FROM recipe WHERE id=%s",
                     (rid,)).fetchone()
    assert rec[0] == "pending_review"  # published → demoted
    assert "蛋" in list(rec[1])


def test_crawler_recipe_content_edit_blocked(db, client):
    rid = mk_recipe(db, title="爬蟲", status="draft")
    r = post(client, f"/admin/recipes/{rid}/content",
             title="x", steps="a",
             ing_name=["a", "b"], ing_qty=["", ""], ing_unit=["", ""],
             ing_note=["", ""], ing_staple=[])
    assert r.status_code == 422 and "不開放" in r.text


def test_export_ingredient_names(db, client):
    _mk(db, "雞蛋", allergen="major_allergen")
    r = client.get("/admin/exports/ingredient-names.csv")
    assert r.status_code == 200 and "雞蛋" in r.text
    assert "staple" in r.text and "ingredient" in r.text


def test_csv_import_preview_and_confirm(db, client):
    _mk(db, "雞蛋"); _mk(db, "鹽")
    recipes = (
        "recipe_id,title,description,cook_time_min,servings,steps,tags,notes\n"
        "imp1,蒸蛋,簡單,15,2,打散||蒸熟,蒸,\n").encode()
    items = ("recipe_id,ingredient_name,qty,unit,note,is_staple\n"
             "imp1,雞蛋,2,顆,,N\nimp1,鹽,,,,Y\n").encode()
    csrf_t = auth.parse_cookie(TOKEN, client.cookies.get(auth.COOKIE_NAME)).csrf
    r = client.post("/admin/recipes/import", data={"csrf": csrf_t}, files={
        "recipes": ("recipes.csv", recipes, "text/csv"),
        "ingredients": ("ingredients.csv", items, "text/csv")})
    assert r.status_code == 200 and "蒸蛋" in r.text and "確認匯入" in r.text
    r = post(client, "/admin/recipes/import/confirm")
    assert r.status_code == 303
    assert one(db, "SELECT count(*) FROM recipe WHERE external_key='imp1'") == 1
    rec = db.execute("SELECT status, is_original, steps FROM recipe"
                     " WHERE external_key='imp1'").fetchone()
    assert rec[0] == "pending_review" and rec[1]
    # confirm again → preview gone → redirect with flash
    r = post(client, "/admin/recipes/import/confirm")
    assert r.status_code == 303


def test_csv_import_rejects_bad_upload(db, client):
    csrf_t = auth.parse_cookie(TOKEN, client.cookies.get(auth.COOKIE_NAME)).csrf
    r = client.post("/admin/recipes/import", data={"csrf": csrf_t}, files={
        "recipes": ("r.exe", b"\xff\xfe", "application/x-msdownload"),
        "ingredients": ("i.csv", b"a,b", "text/csv")})
    assert r.status_code == 422
    r = client.post("/admin/recipes/import", data={"csrf": csrf_t}, files={
        "recipes": ("r.csv", b"wrong,header\n1,2", "text/csv"),
        "ingredients": ("i.csv", b"recipe_id,ingredient_name,qty,unit,note,is_staple\n", "text/csv")})
    assert r.status_code == 422


def test_recipe_list_original_filter(db, client):
    mk_recipe(db, title="爬蟲菜", status="draft")
    r = client.get("/admin/recipes?original=0")
    assert "爬蟲菜" in r.text
    r = client.get("/admin/recipes?original=1")
    assert "爬蟲菜" not in r.text


# --------------------------------------------------------------------------
# Quick review on the ingredients list (v0.9.1)
# --------------------------------------------------------------------------

def test_quick_review_success(db, client):
    iid = mk_ing(db, "白菜")
    r = post(client, f"/admin/ingredients/{iid}/quick-review",
             action="review", next="/admin/ingredients")
    assert r.status_code == 303 and r.headers["location"] == "/admin/ingredients"
    row = db.execute(
        "SELECT reviewed, reviewed_at FROM ingredient WHERE id=%s", (iid,)
    ).fetchone()
    assert row[0] and row[1] is not None
    assert one(db, "SELECT count(*) FROM audit_log WHERE entity_id=%s"
               " AND action='review'", iid) == 1


def test_quick_review_rule_violations_no_change(db, client):
    cases = []
    i1 = mk_ing(db, "缺原因"); db.execute(
        "UPDATE ingredient SET eczema_rating='caution' WHERE id=%s", (i1,))
    cases.append((i1, "評級原因"))
    i2 = mk_ing(db, "缺證據"); db.execute(
        "UPDATE ingredient SET eczema_rating='trigger', rating_reason='x'"
        " WHERE id=%s", (i2,))
    cases.append((i2, "證據"))
    i3 = mk_ing(db, "大豆"); db.execute(
        "INSERT INTO ingredient_allergen (ingredient_id, allergen_id)"
        " SELECT %s, id FROM allergen WHERE type='major_allergen' LIMIT 1", (i3,))
    cases.append((i3, "過敏原"))
    i4 = mk_ing(db, "禁用詞"); db.execute(
        "UPDATE ingredient SET eczema_rating='caution', rating_reason='治療'"
        " WHERE id=%s", (i4,))
    cases.append((i4, "用語"))
    for iid, hint in cases:
        r = post(client, f"/admin/ingredients/{iid}/quick-review",
                 action="review", next="/admin/ingredients")
        assert r.status_code == 303
        assert db.execute(
            "SELECT reviewed FROM ingredient WHERE id=%s", (iid,)
        ).fetchone()[0] is False, hint
        assert one(db, "SELECT count(*) FROM audit_log WHERE entity_id=%s"
                   " AND action='review'", iid) == 0
    page = client.get("/admin/ingredients").text
    assert "缺原因" in page or "評級原因" in page  # flash surfaced


def test_quick_review_csrf_and_login(client):
    iid_resp = client.get("/admin/ingredients")
    login_cookie = client.cookies.get(auth.COOKIE_NAME)
    assert iid_resp.status_code == 200
    client.cookies.clear()
    r = client.post("/admin/ingredients/1/quick-review",
                    data={"action": "review"})
    assert r.status_code == 303  # require_session redirects to login
    client.cookies.set(auth.COOKIE_NAME, login_cookie, path="/admin")
    r = client.post("/admin/ingredients/1/quick-review",
                    data={"action": "review"})  # no csrf
    assert r.status_code == 403


def test_quick_review_404_and_next_whitelist(db, client):
    r = post(client, "/admin/ingredients/999999/quick-review",
             action="review", next="/admin/ingredients")
    assert r.status_code == 404
    iid = mk_ing(db, "跳轉測試")
    for bad in ("https://evil.com", "//evil.com", "/admin/recipes",
                "javascript:alert(1)", ""):
        r = post(client, f"/admin/ingredients/{iid}/quick-review",
                 action="review", next=bad)
        assert r.headers["location"] == "/admin/ingredients", bad
        db.execute("UPDATE ingredient SET reviewed=false WHERE id=%s", (iid,))
    ok = "/admin/ingredients?review=senior&page=2&q=%E9%9B%9E"
    r = post(client, f"/admin/ingredients/{iid}/quick-review",
             action="review", next=ok)
    assert r.headers["location"] == ok


def test_quick_unreview_and_idempotent(db, client):
    iid = _mk(db, "冪等測試", reviewed=True)
    post(client, f"/admin/ingredients/{iid}/quick-review",
         action="review", next="/admin/ingredients")
    assert one(db, "SELECT count(*) FROM audit_log WHERE entity_id=%s"
               " AND action='review'", iid) == 0  # already reviewed → no audit
    post(client, f"/admin/ingredients/{iid}/quick-review",
         action="unreview", next="/admin/ingredients")
    assert db.execute(
        "SELECT reviewed FROM ingredient WHERE id=%s", (iid,)
    ).fetchone()[0] is False
    assert one(db, "SELECT count(*) FROM audit_log WHERE entity_id=%s"
               " AND action='unreview'", iid) == 1
    post(client, f"/admin/ingredients/{iid}/quick-review",
         action="unreview", next="/admin/ingredients")
    assert one(db, "SELECT count(*) FROM audit_log WHERE entity_id=%s"
               " AND action='unreview'", iid) == 1  # second is no-op
