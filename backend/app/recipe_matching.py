"""Pure recipe-matching logic (no DB) — safety-critical, exhaustively tested.

Rules (frozen by unit tests):
- coverage = selected non-staple hits / recipe non-staple item count
  (non-staple recipe_ingredient rows + len(unmatched_ingredients);
  unmatched items count toward the denominator — never inflate coverage;
  unmatched_staples never count anywhere).
- 0 hits or 0 denominator → recipe is not a suggestion.
- exclude_allergens is a HARD exclusion against the union of matched
  ingredients' allergens (ingredient_allergen, incl. staples) and
  allergen_hints names mapped to allergen.name_zh. Unmappable hint names
  are "possibly hit": never excluded, never silent — surfaced as
  unknown_allergen_hints and allergen_warning=True.
- allergen_warning = recipe allergen union non-empty OR contains a
  trigger-rated ingredient; `allergens` is always listed in full.
- rank_score = coverage × (eczema_friendly_score/100 or 0.5 when NULL);
  order: rank_score desc → coverage desc → id asc (deterministic).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AllergenRef:
    id: int
    name_zh: str


@dataclass
class SelectedIngredient:
    id: int
    name_zh: str
    eczema_rating: str
    rating_label: str
    allergens: list[AllergenRef] = field(default_factory=list)


@dataclass
class RecipeFacts:
    id: int
    title: str
    description: str | None
    cook_time: int | None
    servings: int | None
    source_url: str | None
    source_name: str | None
    license: str | None
    tags: list[str]
    status: str
    friendly_score: float | None
    # (ingredient_id, name_zh, is_staple, raw_text, rating)
    matched: list[tuple[int, str, bool, str, str]]
    unmatched: list[str]
    unmatched_staples: list[str]
    hints: list[str]
    # union over matched ingredients (incl. staples): allergen id → name_zh
    allergens: dict[int, str]
    trigger_ingredients: list[str]


def selection_warnings(sel: list[SelectedIngredient]) -> list[dict]:
    """Warn for any selected ingredient rated trigger or carrying allergens
    (a caution item with allergens still warns — only suitable+no allergen
    is quiet)."""
    out = []
    for s in sel:
        reasons = []
        if s.eczema_rating == "trigger":
            reasons.append("rating_trigger")
        if s.allergens:
            reasons.append("has_allergen")
        if reasons:
            out.append({
                "ingredient_id": s.id,
                "name_zh": s.name_zh,
                "eczema_rating": s.eczema_rating,
                "reasons": reasons,
                "allergens": [
                    {"id": a.id, "name_zh": a.name_zh} for a in s.allergens],
            })
    return out


def coverage(selected_ids: set[int], recipe: RecipeFacts) -> float | None:
    """Selected non-staple hits / non-staple total; None → not suggestable."""
    total = sum(1 for m in recipe.matched if not m[2]) + len(recipe.unmatched)
    if total == 0:
        return None
    hits = sum(1 for m in recipe.matched
               if not m[2] and m[0] in selected_ids)
    return None if hits == 0 else hits / total


def evaluate(
    selected_ids: set[int],
    recipe: RecipeFacts,
    excluded_ids: set[int],
    allergen_name_to_id: dict[str, int],
) -> dict | None:
    """Suggest-row dict, or None when excluded/not suggestable.

    Caller counts exclusions via the sentinel ``{"__excluded__": True}`` —
    kept inside the result instead of a second return channel so callers
    cannot silently drop it.
    """
    cov = coverage(selected_ids, recipe)
    if cov is None:
        return None
    hint_ids, unknown = set(), []
    for h in recipe.hints:
        hid = allergen_name_to_id.get(h)
        if hid is None:
            unknown.append(h)
        else:
            hint_ids.add(hid)
    if excluded_ids & (set(recipe.allergens) | hint_ids):
        return {"__excluded__": True}
    score = (recipe.friendly_score / 100.0) if recipe.friendly_score is not None else 0.5
    missing = [m[1] for m in recipe.matched
               if not m[2] and m[0] not in selected_ids] + list(recipe.unmatched)
    names = sorted(set(recipe.allergens.values()) | set(recipe.hints))
    warning = bool(names) or bool(recipe.trigger_ingredients) or bool(unknown)
    out = {
        "id": recipe.id, "title": recipe.title,
        "description": recipe.description, "cook_time": recipe.cook_time,
        "servings": recipe.servings, "source_url": recipe.source_url,
        "source_name": recipe.source_name, "license": recipe.license,
        "tags": recipe.tags,
        "coverage": cov,
        "matched": [
            {"ingredient_id": m[0], "name_zh": m[1]}
            for m in recipe.matched if m[0] in selected_ids],
        "missing": missing,
        "allergens": names,
        "allergen_warning": warning,
        "trigger_ingredients": recipe.trigger_ingredients,
        "unmatched_ingredients": list(recipe.unmatched),
        "unknown_allergen_hints": unknown or None,
        "rank_score": cov * score,
        "draft": recipe.status != "published" or bool(recipe.unmatched),
    }
    return out


def sort_recipes(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (-r["rank_score"], -r["coverage"], r["id"]))
