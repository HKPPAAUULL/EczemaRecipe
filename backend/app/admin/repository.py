"""SQL for the admin backend. Mutations validate with rules.py BEFORE writing,
lock the target row (FOR UPDATE), and always append to audit_log.

Mutating functions return a list of Chinese error messages (empty = success);
on errors nothing has been written.
"""

import psycopg
from psycopg.types.json import Jsonb

from app.admin import rules
from app.repository import like_escape

PAGE_SIZE = 30
INGREDIENT_REVIEW_FILTERS = ("unreviewed", "senior", "unrated", "reviewed", "all")
RECIPE_STATUSES = ("draft", "pending_review", "published", "rejected")


def audit(conn, entity_type: str, entity_id: int, action: str, detail: dict) -> None:
    conn.execute(
        "INSERT INTO audit_log (entity_type, entity_id, action, detail)"
        " VALUES (%s, %s, %s, %s)",
        (entity_type, entity_id, action, Jsonb(detail)),
    )


def _offset(page: int) -> int:
    return (max(page, 1) - 1) * PAGE_SIZE


def dashboard_counts(conn) -> dict:
    return conn.execute(
        """
        SELECT
          (SELECT count(*) FROM ingredient WHERE NOT reviewed) AS ing_unreviewed,
          (SELECT count(*) FROM ingredient WHERE NOT reviewed AND needs_senior_review) AS ing_senior,
          (SELECT count(*) FROM ingredient WHERE NOT reviewed AND eczema_rating = 'unrated') AS ing_unrated,
          (SELECT count(*) FROM recipe WHERE status IN ('pending_review', 'draft')) AS rec_pending,
          (SELECT count(*) FROM recipe WHERE cardinality(unmatched_ingredients) > 0) AS rec_unmatched,
          (SELECT count(*) FROM review_queue WHERE status = 'pending') AS queue_pending
        """
    ).fetchone()


def list_categories(conn) -> list[dict]:
    return conn.execute(
        "SELECT id, name_zh FROM food_category ORDER BY sort_order, name_zh"
    ).fetchall()


def list_allergens(conn) -> list[dict]:
    return conn.execute("SELECT id, name_zh, type FROM allergen ORDER BY id").fetchall()


def list_ingredients(
    conn, review: str, rating: str, category_id: int | None, q: str, page: int
) -> tuple[int, list[dict]]:
    where, params = ["true"], {}
    if review == "unreviewed":
        where.append("NOT i.reviewed")
    elif review == "senior":
        where.append("NOT i.reviewed AND i.needs_senior_review")
    elif review == "unrated":
        where.append("NOT i.reviewed AND i.eczema_rating = 'unrated'")
    elif review == "reviewed":
        where.append("i.reviewed")
    if rating in rules.RATINGS:
        where.append("i.eczema_rating = %(rating)s")
        params["rating"] = rating
    if category_id is not None:
        where.append("i.category_id = %(cid)s")
        params["cid"] = category_id
    if q:
        where.append(
            "(i.name_zh ILIKE %(pat)s ESCAPE '\' OR aliases_text(i.aliases) ILIKE %(pat)s ESCAPE '\')"
        )
        params["pat"] = f"%{like_escape(q)}%"
    clause = " AND ".join(where)
    total = conn.execute(
        f"SELECT count(*) AS n FROM ingredient i WHERE {clause}", params
    ).fetchone()["n"]
    rows = conn.execute(
        f"""
        SELECT i.id, i.name_zh, i.eczema_rating, i.reviewed, i.needs_senior_review,
               c.name_zh AS category_name,
               COALESCE((SELECT array_agg(a.name_zh ORDER BY a.id)
                           FROM ingredient_allergen ia JOIN allergen a ON a.id = ia.allergen_id
                          WHERE ia.ingredient_id = i.id), '{{}}') AS allergens
          FROM ingredient i LEFT JOIN food_category c ON c.id = i.category_id
         WHERE {clause}
         ORDER BY i.needs_senior_review DESC, i.id
         LIMIT {PAGE_SIZE} OFFSET {_offset(page)}""",
        params,
    ).fetchall()
    return total, rows


def get_ingredient(conn, iid: int, lock: bool = False) -> dict | None:
    return conn.execute(
        "SELECT * FROM ingredient WHERE id = %s" + (" FOR UPDATE" if lock else ""), (iid,)
    ).fetchone()


def get_ingredient_detail(conn, iid: int) -> dict | None:
    ing = conn.execute(
        """SELECT i.*, c.name_zh AS category_name FROM ingredient i
             LEFT JOIN food_category c ON c.id = i.category_id WHERE i.id = %s""",
        (iid,),
    ).fetchone()
    if ing is None:
        return None
    ing["allergens"] = conn.execute(
        """SELECT a.id, a.name_zh, a.type, ia.severity FROM ingredient_allergen ia
             JOIN allergen a ON a.id = ia.allergen_id
            WHERE ia.ingredient_id = %s ORDER BY a.id""",
        (iid,),
    ).fetchall()
    ing["evidence"] = conn.execute(
        "SELECT id, title, url, source_type, year FROM evidence WHERE ingredient_id = %s ORDER BY id",
        (iid,),
    ).fetchall()
    ing["nutrients"] = conn.execute(
        """SELECT n.name, n.unit, iv.amount_per_100g, ds.name AS source, ds.url AS source_url
             FROM ingredient_nutrient iv JOIN nutrient n ON n.id = iv.nutrient_id
             LEFT JOIN data_source ds ON ds.id = iv.source_id
            WHERE iv.ingredient_id = %s ORDER BY n.name""",
        (iid,),
    ).fetchall()
    ing["published_recipe_count"] = conn.execute(
        """SELECT count(*) AS n FROM recipe_ingredient ri
             JOIN published_recipe r ON r.id = ri.recipe_id WHERE ri.ingredient_id = %s""",
        (iid,),
    ).fetchone()["n"]
    ing["audit"] = conn.execute(
        """SELECT action, detail, created_at FROM audit_log
            WHERE entity_type = 'ingredient' AND entity_id = %s ORDER BY id DESC LIMIT 15""",
        (iid,),
    ).fetchall()
    return ing


def _evidence_urls(conn, iid: int) -> list[str | None]:
    return [r["url"] for r in conn.execute(
        "SELECT url FROM evidence WHERE ingredient_id = %s", (iid,)).fetchall()]


def _has_major_allergen(conn, iid: int) -> bool:
    return conn.execute(
        """SELECT EXISTS (SELECT 1 FROM ingredient_allergen ia
                            JOIN allergen a ON a.id = ia.allergen_id
                           WHERE ia.ingredient_id = %s AND a.type = 'major_allergen') AS x""",
        (iid,),
    ).fetchone()["x"]


def _invalidate_review(conn, iid: int, why: str) -> bool:
    row = conn.execute(
        "UPDATE ingredient SET reviewed = false, reviewed_at = NULL"
        " WHERE id = %s AND reviewed RETURNING id",
        (iid,),
    ).fetchone()
    if row:
        audit(conn, "ingredient", iid, "auto_unreview", {"why": why})
    return row is not None


def save_ingredient(
    conn, iid: int, rating: str, reason: str, senior: bool,
    category_id: int | None, aliases: list[str],
) -> tuple[list[str], bool]:
    """Returns (errors, review_was_reset)."""
    old = get_ingredient(conn, iid, lock=True)
    if old is None:
        return ["找不到食材。"], False
    reason = reason.strip()
    errors = rules.validate_ingredient_fields(rating, reason)
    if category_id is not None and conn.execute(
        "SELECT 1 FROM food_category WHERE id = %s", (category_id,)
    ).fetchone() is None:
        errors.append("分類不存在。")
    if errors:
        return errors, False
    conn.execute(
        """UPDATE ingredient SET eczema_rating = %s, rating_reason = %s,
                  needs_senior_review = %s, category_id = %s, aliases = %s WHERE id = %s""",
        (rating, reason or None, senior, category_id, aliases, iid),
    )
    audit(conn, "ingredient", iid, "edit", {
        "rating": [old["eczema_rating"], rating],
        "rating_reason": [old["rating_reason"], reason or None],
        "needs_senior_review": [old["needs_senior_review"], senior],
        "category_id": [old["category_id"], category_id],
        "aliases": [list(old["aliases"]), aliases],
    })
    critical = (old["eczema_rating"] != rating
                or (old["rating_reason"] or "") != reason)
    reset = _invalidate_review(conn, iid, "rating/reason edited") if critical else False
    return [], reset


def add_allergen(conn, iid: int, allergen_id: int, severity: str | None) -> tuple[list[str], bool]:
    if get_ingredient(conn, iid, lock=True) is None:
        return ["找不到食材。"], False
    if severity and severity not in rules.SEVERITIES:
        return ["嚴重度無效。"], False
    allergen = conn.execute(
        "SELECT name_zh FROM allergen WHERE id = %s", (allergen_id,)
    ).fetchone()
    if allergen is None:
        return ["過敏原不存在。"], False
    conn.execute(
        """INSERT INTO ingredient_allergen (ingredient_id, allergen_id, severity)
           VALUES (%s, %s, %s) ON CONFLICT (ingredient_id, allergen_id)
           DO UPDATE SET severity = EXCLUDED.severity""",
        (iid, allergen_id, severity or None),
    )
    audit(conn, "ingredient", iid, "allergen_set",
          {"allergen": allergen["name_zh"], "severity": severity or None})
    return [], _invalidate_review(conn, iid, "allergen changed")


def delete_allergen(conn, iid: int, allergen_id: int) -> tuple[list[str], bool]:
    if get_ingredient(conn, iid, lock=True) is None:
        return ["找不到食材。"], False
    row = conn.execute(
        """DELETE FROM ingredient_allergen WHERE ingredient_id = %s AND allergen_id = %s
           RETURNING (SELECT name_zh FROM allergen WHERE id = %s) AS name""",
        (iid, allergen_id, allergen_id),
    ).fetchone()
    if row is None:
        return ["找不到該過敏原連結。"], False
    audit(conn, "ingredient", iid, "allergen_delete", {"allergen": row["name"]})
    return [], _invalidate_review(conn, iid, "allergen changed")


def add_evidence(conn, iid: int, title, url, source_type, year_raw) -> tuple[list[str], bool]:
    if get_ingredient(conn, iid, lock=True) is None:
        return ["找不到食材。"], False
    clean, errors = rules.validate_evidence(title, url, source_type, year_raw)
    if errors:
        return errors, False
    try:
        with conn.transaction():
            conn.execute(
                """INSERT INTO evidence (ingredient_id, title, url, source_type, year)
                   VALUES (%(iid)s, %(title)s, %(url)s, %(source_type)s, %(year)s)""",
                {"iid": iid, **clean},
            )
    except psycopg.errors.UniqueViolation:
        return ["此食材已有相同網址的證據。"], False
    audit(conn, "ingredient", iid, "evidence_add", clean)
    return [], _invalidate_review(conn, iid, "evidence changed")


def delete_evidence(conn, iid: int, evidence_id: int) -> tuple[list[str], bool]:
    if get_ingredient(conn, iid, lock=True) is None:
        return ["找不到食材。"], False
    row = conn.execute(
        "DELETE FROM evidence WHERE id = %s AND ingredient_id = %s RETURNING title, url",
        (evidence_id, iid),
    ).fetchone()
    if row is None:
        return ["找不到該證據。"], False
    audit(conn, "ingredient", iid, "evidence_delete", dict(row))
    return [], _invalidate_review(conn, iid, "evidence changed")


def set_ingredient_reviewed(conn, iid: int, reviewed: bool) -> list[str]:
    ing = get_ingredient(conn, iid, lock=True)
    if ing is None:
        return ["找不到食材。"]
    if reviewed:
        errors = rules.validate_ingredient_review(
            ing["eczema_rating"], ing["rating_reason"],
            _has_major_allergen(conn, iid), _evidence_urls(conn, iid),
        )
        if errors:
            return errors
        conn.execute(
            "UPDATE ingredient SET reviewed = true, reviewed_at = now() WHERE id = %s", (iid,))
        conn.execute(
            """UPDATE review_queue SET status = 'approved'
                WHERE entity_type = 'ingredient' AND entity_id = %s AND status = 'pending'""",
            (iid,),
        )
        audit(conn, "ingredient", iid, "review", {"rating": ing["eczema_rating"]})
    else:
        conn.execute(
            "UPDATE ingredient SET reviewed = false, reviewed_at = NULL WHERE id = %s", (iid,))
        audit(conn, "ingredient", iid, "unreview", {})
    return []


def list_recipes(
    conn, status: str, unmatched: bool, q: str, page: int
) -> tuple[int, list[dict]]:
    where, params = ["true"], {}
    if status in RECIPE_STATUSES:
        where.append("r.status = %(status)s")
        params["status"] = status
    if unmatched:
        where.append("cardinality(r.unmatched_ingredients) > 0")
    if q:
        where.append("r.title ILIKE %(pat)s ESCAPE '\'")
        params["pat"] = f"%{like_escape(q)}%"
    clause = " AND ".join(where)
    total = conn.execute(
        f"SELECT count(*) AS n FROM recipe r WHERE {clause}", params
    ).fetchone()["n"]
    rows = conn.execute(
        f"""SELECT r.id, r.title, r.status, r.eczema_friendly_score,
                   cardinality(r.unmatched_ingredients) AS unmatched_count,
                   cardinality(r.allergen_hints) AS hint_count
              FROM recipe r WHERE {clause}
             ORDER BY r.id LIMIT {PAGE_SIZE} OFFSET {_offset(page)}""",
        params,
    ).fetchall()
    return total, rows


def get_recipe(conn, rid: int, lock: bool = False) -> dict | None:
    return conn.execute(
        "SELECT * FROM recipe WHERE id = %s" + (" FOR UPDATE" if lock else ""), (rid,)
    ).fetchone()


def _matched(conn, rid: int) -> list[dict]:
    return conn.execute(
        """SELECT ri.ingredient_id, ri.raw_text, ri.is_staple, i.name_zh, i.eczema_rating,
                  i.reviewed,
                  COALESCE((SELECT array_agg(a.name_zh ORDER BY a.id)
                              FROM ingredient_allergen ia JOIN allergen a ON a.id = ia.allergen_id
                             WHERE ia.ingredient_id = i.id), '{}') AS allergens
             FROM recipe_ingredient ri JOIN ingredient i ON i.id = ri.ingredient_id
            WHERE ri.recipe_id = %s ORDER BY ri.is_staple, i.name_zh""",
        (rid,),
    ).fetchall()


def get_recipe_detail(conn, rid: int) -> dict | None:
    rec = conn.execute(
        """SELECT r.*, ds.name AS source_name, ds.url AS source_site, ds.license AS source_license
             FROM recipe r LEFT JOIN data_source ds ON ds.id = r.data_source_id WHERE r.id = %s""",
        (rid,),
    ).fetchone()
    if rec is None:
        return None
    rec["matched"] = _matched(conn, rid)
    rec["tags"] = [t["tag"] for t in conn.execute(
        "SELECT tag FROM recipe_tag WHERE recipe_id = %s ORDER BY tag", (rid,)).fetchall()]
    rec["queue"] = conn.execute(
        "SELECT id, status, reviewer_note, created_at FROM review_queue"
        " WHERE entity_type = 'recipe' AND entity_id = %s ORDER BY id DESC", (rid,)).fetchall()
    rec["audit"] = conn.execute(
        """SELECT action, detail, created_at FROM audit_log
            WHERE entity_type = 'recipe' AND entity_id = %s ORDER BY id DESC LIMIT 15""",
        (rid,)).fetchall()
    rec["publish_errors"] = rules.validate_publish(
        list(rec["unmatched_ingredients"]), rec["matched"])
    return rec


def search_ingredients(conn, q: str, limit: int = 20) -> list[dict]:
    if not q:
        return []
    return conn.execute(
        """SELECT id, name_zh, eczema_rating, reviewed FROM ingredient
            WHERE name_zh ILIKE %(pat)s ESCAPE '\' OR aliases_text(aliases) ILIKE %(pat)s ESCAPE '\'
            ORDER BY (name_zh = %(q)s) DESC, name_zh LIMIT %(limit)s""",
        {"pat": f"%{like_escape(q)}%", "q": q, "limit": limit},
    ).fetchall()


def list_queue(conn, page: int) -> tuple[int, list[dict]]:
    total = conn.execute(
        "SELECT count(*) AS n FROM review_queue WHERE status = 'pending'").fetchone()["n"]
    rows = conn.execute(
        f"""SELECT q.id, q.entity_type, q.entity_id, q.reviewer_note, q.created_at,
                   CASE q.entity_type
                        WHEN 'recipe' THEN (SELECT title FROM recipe WHERE id = q.entity_id)
                        WHEN 'ingredient' THEN (SELECT name_zh FROM ingredient WHERE id = q.entity_id)
                   END AS label
              FROM review_queue q WHERE q.status = 'pending'
             ORDER BY q.id LIMIT {PAGE_SIZE} OFFSET {_offset(page)}"""
    ).fetchall()
    return total, rows


def _recipe_queue(conn, rid: int, note: str, final: str | None = None) -> None:
    row = conn.execute(
        """SELECT id FROM review_queue
            WHERE entity_type = 'recipe' AND entity_id = %s AND status = 'pending'
            ORDER BY id DESC LIMIT 1 FOR UPDATE""",
        (rid,),
    ).fetchone()
    stamp = conn.execute("SELECT to_char(now(), 'YYYY-MM-DD HH24:MI') AS ts").fetchone()["ts"]
    line = f"[{stamp}] {note}"
    if row:
        conn.execute(
            """UPDATE review_queue
                  SET reviewer_note = CASE WHEN coalesce(reviewer_note, '') = '' THEN %(line)s
                                           ELSE reviewer_note || E'\n' || %(line)s END,
                      status = coalesce(%(final)s::review_status, status)
                WHERE id = %(id)s""",
            {"line": line, "final": final, "id": row["id"]},
        )
        return
    if final is None:
        recipe_status = conn.execute(
            "SELECT status FROM recipe WHERE id = %s", (rid,)).fetchone()["status"]
        final = {"published": "approved", "rejected": "rejected"}.get(recipe_status, "pending")
    conn.execute(
        "INSERT INTO review_queue (entity_type, entity_id, status, reviewer_note)"
        " VALUES ('recipe', %s, %s, %s)",
        (rid, final, line),
    )


def map_unmatched(conn, rid: int, item: str, ingredient_id: int, is_staple: bool) -> list[str]:
    rec = get_recipe(conn, rid, lock=True)
    if rec is None:
        return ["找不到食譜。"]
    if item not in list(rec["unmatched_ingredients"]):
        return ["找不到該未配對項目（可能已被處理）。"]
    ing = conn.execute(
        "SELECT name_zh FROM ingredient WHERE id = %s", (ingredient_id,)
    ).fetchone()
    if ing is None:
        return ["請先搜尋並選擇有效的食材。"]
    existing = conn.execute(
        "SELECT raw_text FROM recipe_ingredient WHERE recipe_id = %s AND ingredient_id = %s",
        (rid, ingredient_id),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE recipe_ingredient SET raw_text = %s WHERE recipe_id = %s AND ingredient_id = %s",
            (rules.merge_raw_text(existing["raw_text"], item), rid, ingredient_id),
        )
    else:
        conn.execute(
            "INSERT INTO recipe_ingredient (recipe_id, ingredient_id, raw_text, is_staple)"
            " VALUES (%s, %s, %s, %s)",
            (rid, ingredient_id, item, is_staple),
        )
    conn.execute(
        "UPDATE recipe SET unmatched_ingredients = %s WHERE id = %s",
        (rules.remove_item(list(rec["unmatched_ingredients"]), item), rid),
    )
    audit(conn, "recipe", rid, "map_unmatched",
          {"item": item, "ingredient": ing["name_zh"], "ingredient_id": ingredient_id,
           "is_staple": is_staple})
    _recipe_queue(conn, rid, f"配對「{item}」→ {ing['name_zh']}")
    return []


def ignore_unmatched(conn, rid: int, item: str, reason: str) -> list[str]:
    reason = reason.strip()
    if not reason:
        return ["忽略未配對項目必須填寫原因。"]
    rec = get_recipe(conn, rid, lock=True)
    if rec is None:
        return ["找不到食譜。"]
    if item not in list(rec["unmatched_ingredients"]):
        return ["找不到該未配對項目（可能已被處理）。"]
    conn.execute(
        "UPDATE recipe SET unmatched_ingredients = %s WHERE id = %s",
        (rules.remove_item(list(rec["unmatched_ingredients"]), item), rid),
    )
    audit(conn, "recipe", rid, "ignore_unmatched", {"item": item, "reason": reason})
    _recipe_queue(conn, rid, f"忽略「{item}」（非食材）：{reason}")
    return []


def staple_unmatched(conn, rid: int, item: str) -> list[str]:
    rec = get_recipe(conn, rid, lock=True)
    if rec is None:
        return ["找不到食譜。"]
    if item not in list(rec["unmatched_ingredients"]):
        return ["找不到該未配對項目（可能已被處理）。"]
    staples = list(rec["unmatched_staples"])
    if item not in staples:
        staples.append(item)
    conn.execute(
        "UPDATE recipe SET unmatched_ingredients = %s, unmatched_staples = %s WHERE id = %s",
        (rules.remove_item(list(rec["unmatched_ingredients"]), item), staples, rid),
    )
    audit(conn
, "recipe", rid, "staple_unmatched", {"item": item})
    _recipe_queue(conn, rid, f"「{item}」移到未配對調味料")
    return []


def edit_recipe(conn, rid: int, description: str, score_raw, cook_raw, servings_raw) -> list[str]:
    rec = get_recipe(conn, rid, lock=True)
    if rec is None:
        return ["找不到食譜。"]
    score, e1 = rules.parse_score(score_raw)
    cook, e2 = rules.parse_positive_int(cook_raw, "烹調時間", 0)
    servings, e3 = rules.parse_positive_int(servings_raw, "份量", 1)
    errors = e1 + e2 + e3
    if errors:
        return errors
    description = description.strip() or None
    old_score = rec["eczema_friendly_score"]
    conn.execute(
        """UPDATE recipe SET description = %s, eczema_friendly_score = %s,
                  cook_time = %s, servings = %s WHERE id = %s""",
        (description, score, cook, servings, rid),
    )
    audit(conn, "recipe", rid, "edit", {
        "description": [rec["description"], description],
        "score": [float(old_score) if old_score is not None else None, score],
        "cook_time": [rec["cook_time"], cook],
        "servings": [rec["servings"], servings],
    })
    _recipe_queue(conn, rid, "編輯食譜資料")
    return []


def change_recipe_status(conn, rid: int, action: str, reason: str) -> list[str]:
    rec = get_recipe(conn, rid, lock=True)
    if rec is None:
        return ["找不到食譜。"]
    err = rules.check_transition(rec["status"], action)
    if err:
        return [err]
    reason = reason.strip()
    if action == "reject" and not reason:
        return ["退回食譜必須填寫原因。"]
    if action == "publish":
        errors = rules.validate_publish(list(rec["unmatched_ingredients"]), _matched(conn, rid))
        if errors:
            return errors
    target = rules.ACTION_TARGET[action]
    conn.execute("UPDATE recipe SET status = %s WHERE id = %s", (target, rid))
    audit(conn, "recipe", rid, action,
          {"from": rec["status"], "to": target, "reason": reason or None})
    final = {"publish": "approved", "reject": "rejected", "resubmit": "pending"}[action]
    note = f"{rules.ACTION_LABELS[action]}（{rec['status']} → {target}）"
    if reason:
        note += f"：{reason}"
    _recipe_queue(conn, rid, note, final)
    return []
