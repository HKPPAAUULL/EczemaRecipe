"""POST /api/recipes/suggest — match pantry ingredients to recipes with
allergen warnings (safety-critical logic lives in app.recipe_matching).
GET /api/recipes/{id} — recipe detail.
"""

from fastapi import APIRouter, HTTPException, Request

from app import repository
from app.deps import db_conn, include_drafts
from app.recipe_matching import (
    AllergenRef,
    RecipeFacts,
    SelectedIngredient,
    evaluate,
    selection_warnings,
    sort_recipes,
)
from app.schemas import (
    RecipeDetailResponse,
    SuggestRequest,
    SuggestResponse,
)

router = APIRouter(prefix="/api/recipes", tags=["recipes"])

_RATING_LABELS = {"suitable": "一般適合", "caution": "因人而異",
                  "trigger": "常見誘因", "unrated": "資料不足"}


def _facts(row, links, allergen_union):
    matched = [
        (l["ingredient_id"], l["name_zh"], l["is_staple"], l["raw_text"],
         l["eczema_rating"]) for l in links.get(row["id"], [])
    ]
    return RecipeFacts(
        id=row["id"], title=row["title"], description=row["description"],
        cook_time=row["cook_time"], servings=row["servings"],
        source_url=row["source_url"], source_name=row["source_name"],
        license=row["source_license"], tags=list(row["tags"] or []),
        status=row["status"],
        friendly_score=(float(row["eczema_friendly_score"])
                        if row["eczema_friendly_score"] is not None else None),
        matched=matched, unmatched=list(row["unmatched_ingredients"] or []),
        unmatched_staples=list(row["unmatched_staples"] or []),
        hints=list(row["allergen_hints"] or []),
        allergens=allergen_union.get(row["id"], {}),
        trigger_ingredients=[
            l["name_zh"] for l in links.get(row["id"], [])
            if l["eczema_rating"] == "trigger"],
        is_original=bool(row["is_original"]),
    )


@router.post("/suggest", response_model=SuggestResponse)
def suggest(payload: SuggestRequest, request: Request):
    drafts = include_drafts(request)
    ids = list(dict.fromkeys(payload.ingredient_ids))
    with db_conn(request) as conn:
        refs = repository.get_ingredient_refs(conn, ids, drafts)
        missing = [i for i in ids if i not in refs]
        if missing:
            raise HTTPException(
                status_code=422,
                detail={"invalid_ingredient_ids": missing})
        amap = {r["id"]: r["name_zh"] for r in conn.execute(
            "SELECT id, name_zh FROM allergen WHERE id = ANY(%(ids)s)",
            {"ids": payload.exclude_allergens})}
        bad = [i for i in payload.exclude_allergens if i not in amap]
        if bad:
            raise HTTPException(
                status_code=422, detail={"invalid_allergen_ids": bad})
        name_to_id = repository.allergen_name_to_id(conn)
        rows = repository.list_recipe_candidates(conn, drafts, ids)
        rids = [r["id"] for r in rows]
        links = repository.list_recipe_links(conn, rids)
        aunion = repository.list_recipe_allergens(conn, rids)

    sel = [
        SelectedIngredient(
            id=r["id"], name_zh=r["name_zh"],
            eczema_rating=r["eczema_rating"], rating_label=r["rating_label"],
            allergens=[AllergenRef(a["id"], a["name_zh"])
                       for a in r["allergens"]])
        for r in (refs[i] for i in ids)
    ]
    idset, excl = set(ids), set(payload.exclude_allergens)
    recipes, excluded = [], 0
    for row in rows:
        out = evaluate(idset, _facts(row, links, aunion), excl, name_to_id)
        if out is None:
            continue
        if out.get("__excluded__"):
            excluded += 1
            continue
        recipes.append(out)
    ordered = sort_recipes(recipes)
    page = ordered[payload.offset: payload.offset + payload.limit]
    return SuggestResponse(
        selected=[refs[i] for i in ids],
        warnings=selection_warnings(sel),
        excluded_by_allergen_count=excluded,
        total=len(ordered), limit=payload.limit, offset=payload.offset,
        recipes=page,
    )


@router.get("/{recipe_id}", response_model=RecipeDetailResponse)
def detail(recipe_id: int, request: Request):
    drafts = include_drafts(request)
    with db_conn(request) as conn:
        row = repository.get_recipe(conn, recipe_id, drafts)
        if row is None:
            raise HTTPException(status_code=404, detail="recipe not found")
        links = repository.list_recipe_links(conn, [recipe_id])
        aunion = repository.list_recipe_allergens(conn, [recipe_id])
        amap = repository._allergen_map(
            conn, [l["ingredient_id"] for l in links.get(recipe_id, [])])
    ingredients = [
        {"ingredient_id": l["ingredient_id"], "name_zh": l["name_zh"],
         "eczema_rating": l["eczema_rating"],
         "rating_label": _RATING_LABELS[l["eczema_rating"]],
         "raw_text": l["raw_text"],
         "qty": float(l["qty"]) if l["qty"] is not None else None,
         "unit": l["unit"], "is_staple": l["is_staple"],
         "allergens": amap.get(l["ingredient_id"], [])}
        for l in links.get(recipe_id, [])
    ]
    union_names = sorted(
        set(aunion.get(recipe_id, {}).values()) | set(row["allergen_hints"] or []))
    warning = bool(union_names) or any(
        l["eczema_rating"] == "trigger" for l in links.get(recipe_id, []))
    return RecipeDetailResponse(
        id=row["id"], title=row["title"], description=row["description"],
        cook_time=row["cook_time"], servings=row["servings"],
        source_url=row["source_url"], source_name=row["source_name"],
        license=row["source_license"], tags=list(row["tags"] or []),
        ingredients=ingredients,
        unmatched_ingredients=list(row["unmatched_ingredients"] or []),
        unmatched_staples=list(row["unmatched_staples"] or []),
        allergens=union_names, allergen_warning=warning,
        draft=row["status"] != "published" or bool(row["unmatched_ingredients"]),
        steps=list(row["steps"] or []), notes=row["notes"],
        is_original=bool(row["is_original"]),
    )
