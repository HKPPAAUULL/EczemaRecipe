"""SQL access layer for the read API (parameterised queries only).

Data visibility (safety-critical): INGREDIENT_RELATION is the single place
deciding which relation ingredient queries read from — `published_ingredient`
(reviewed=true only) when drafts are off, `ingredient` when on. The value is a
compile-time whitelist key, never user input.
"""

from app.schemas import RATING_LABELS

INGREDIENT_RELATION = {True: "ingredient", False: "published_ingredient"}


def like_escape(q: str) -> str:
    """Escape %, _ and \\ for use in ILIKE ... ESCAPE '\\' patterns."""
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


_LIST_SELECT = """
    SELECT i.id, i.name_zh, i.name_en, i.eczema_rating, i.reviewed,
           c.id AS category_id, c.name_zh AS category_name_zh,
           COALESCE((
               SELECT array_agg(a.name_zh ORDER BY a.id)
               FROM ingredient_allergen ia
               JOIN allergen a ON a.id = ia.allergen_id
              WHERE ia.ingredient_id = i.id
           ), '{}') AS allergens
      FROM {rel} AS i
      LEFT JOIN food_category c ON c.id = i.category_id
"""


def _to_list_item(row) -> dict:
    return {
        "id": row["id"],
        "name_zh": row["name_zh"],
        "name_en": row["name_en"],
        "category": (
            {"id": row["category_id"], "name_zh": row["category_name_zh"]}
            if row["category_id"] is not None
            else None
        ),
        "eczema_rating": row["eczema_rating"],
        "rating_label": RATING_LABELS[row["eczema_rating"]],
        "allergens": list(row["allergens"] or []),
        "draft": not row["reviewed"],
    }


def search_ingredients(conn, q: str, limit: int, include_drafts: bool) -> list[dict]:
    rel = INGREDIENT_RELATION[include_drafts]
    rows = conn.execute(
        _LIST_SELECT.format(rel=rel)
        + """
     WHERE i.name_zh ILIKE %(pat)s ESCAPE '\\'
        OR aliases_text(i.aliases) ILIKE %(pat)s ESCAPE '\\'
     ORDER BY CASE
             WHEN lower(i.name_zh) = lower(%(q)s) THEN 0
             WHEN EXISTS (
                     SELECT 1 FROM unnest(i.aliases) AS u(x)
                     WHERE lower(u.x) = lower(%(q)s)
                  ) THEN 1
             WHEN i.name_zh ILIKE %(prefix)s ESCAPE '\\' THEN 2
             ELSE 3
         END,
         i.name_zh
     LIMIT %(limit)s""",
        {
            "pat": f"%{like_escape(q)}%",
            "prefix": f"{like_escape(q)}%",
            "q": q,
            "limit": limit,
        },
    ).fetchall()
    return [_to_list_item(r) for r in rows]


def get_ingredient_detail(conn, ingredient_id: int, include_drafts: bool) -> dict | None:
    rel = INGREDIENT_RELATION[include_drafts]
    row = conn.execute(
        f"""
        SELECT i.*, c.id AS cat_id, c.name_zh AS cat_name
          FROM {rel} AS i
          LEFT JOIN food_category c ON c.id = i.category_id
         WHERE i.id = %(iid)s""",
        {"iid": ingredient_id},
    ).fetchone()
    if row is None:
        return None

    rating = row["eczema_rating"]
    allergens = conn.execute(
        """
        SELECT a.id, a.name_zh, a.type, ia.severity
          FROM ingredient_allergen ia
          JOIN allergen a ON a.id = ia.allergen_id
         WHERE ia.ingredient_id = %(iid)s
         ORDER BY a.id""",
        {"iid": ingredient_id},
    ).fetchall()
    evidence = conn.execute(
        """
        SELECT title, url, source_type, year
          FROM evidence
         WHERE ingredient_id = %(iid)s
         ORDER BY id""",
        {"iid": ingredient_id},
    ).fetchall()
    nutrients = conn.execute(
        """
        SELECT n.name, n.unit, iv.amount_per_100g, ds.name AS source
          FROM ingredient_nutrient iv
          JOIN nutrient n ON n.id = iv.nutrient_id
          LEFT JOIN data_source ds ON ds.id = iv.source_id
         WHERE iv.ingredient_id = %(iid)s
         ORDER BY n.name""",
        {"iid": ingredient_id},
    ).fetchall()

    # 'unrated' must not leak draft rating guesses (RATING_CRITERIA §2)
    reason = row["rating_reason"] if rating != "unrated" else None
    return {
        "id": row["id"],
        "name_zh": row["name_zh"],
        "name_en": row["name_en"],
        "aliases": list(row["aliases"] or []),
        "category": (
            {"id": row["cat_id"], "name_zh": row["cat_name"]}
            if row["cat_id"] is not None
            else None
        ),
        "eczema_rating": rating,
        "rating_label": RATING_LABELS[rating],
        "rating_reason": reason,
        "allergens": [
            {
                "id": a["id"],
                "name_zh": a["name_zh"],
                "type": a["type"],
                "severity": a["severity"],
            }
            for a in allergens
        ],
        "evidence": [
            {
                "title": e["title"],
                "url": e["url"],
                "source_type": e["source_type"],
                "year": e["year"],
            }
            for e in evidence
        ],
        "nutrients": [
            {
                "name": n["name"],
                "unit": n["unit"],
                "amount_per_100g": n["amount_per_100g"],
                "source": n["source"],
            }
            for n in nutrients
        ],
        "needs_senior_review": (
            row["needs_senior_review"] if include_drafts else None
        ),
        "draft": not row["reviewed"],
        "updated_at": row["updated_at"],
    }


def list_categories(conn, include_drafts: bool) -> list[dict]:
    rel = INGREDIENT_RELATION[include_drafts]
    rows = conn.execute(
        f"""
        SELECT c.id, c.name_zh, c.sort_order, count(i.id) AS ingredient_count
          FROM food_category c
          LEFT JOIN {rel} AS i ON i.category_id = c.id
         GROUP BY c.id
         ORDER BY c.sort_order, c.name_zh""",
    ).fetchall()
    return [dict(r) for r in rows]


def get_category(conn, category_id: int) -> dict | None:
    return conn.execute(
        "SELECT id, name_zh FROM food_category WHERE id = %(cid)s",
        {"cid": category_id},
    ).fetchone()


def list_category_ingredients(
    conn, category_id: int, rating: str | None, limit: int, offset: int, include_drafts: bool
) -> tuple[int, list[dict]]:
    rel = INGREDIENT_RELATION[include_drafts]
    where = "WHERE i.category_id = %(cid)s"
    params: dict = {"cid": category_id, "limit": limit, "offset": offset}
    if rating:
        where += " AND i.eczema_rating = %(rating)s"
        params["rating"] = rating
    total = conn.execute(
        f"SELECT count(*) AS n FROM {rel} AS i {where}", params
    ).fetchone()["n"]
    rows = conn.execute(
        _LIST_SELECT.format(rel=rel)
        + where
        + " ORDER BY i.name_zh LIMIT %(limit)s OFFSET %(offset)s",
        params,
    ).fetchall()
    return total, [_to_list_item(r) for r in rows]


def list_allergens(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name_zh, name_en, type FROM allergen ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]
