"""Unit tests for app.recipe_matching — pure logic, no DB."""

from app.recipe_matching import (
    AllergenRef,
    RecipeFacts,
    SelectedIngredient,
    coverage,
    evaluate,
    selection_warnings,
    sort_recipes,
)

A_EGG = AllergenRef(1, "蛋")
A_MILK = AllergenRef(2, "奶")


def _recipe(**kw):
    base = {
        "id": 1, "title": "r", "description": None, "cook_time": None,
        "servings": None, "source_url": None, "source_name": None,
        "license": None, "tags": [], "status": "published",
        "friendly_score": None, "matched": [], "unmatched": [],
        "unmatched_staples": [], "hints": [], "allergens": {},
        "trigger_ingredients": [],
    }
    base.update(kw)
    return RecipeFacts(**base)


def test_coverage_excludes_staples_and_counts_unmatched():
    # 2 non-staple matched (雞胸肉 hit, 番茄 miss) + 1 staple (鹽) + 1 unmatched
    r = _recipe(matched=[(10, "雞胸肉", False, "", ""), (11, "番茄", False, "", ""),
                        (12, "鹽", True, "", "")],
                unmatched=["神秘菜"])
    # denominator = 2 non-staple matched + 1 unmatched = 3; hits = 1 → 1/3
    assert coverage({10}, r) == 1 / 3
    assert coverage({10, 12}, r) == 1 / 3   # staple hit doesn't count
    assert coverage({10, 11}, r) == 2 / 3
    assert coverage({99}, r) is None        # 0 hits → not suggestable
    assert coverage(set(), r) is None


def test_coverage_zero_denominator_excluded():
    r = _recipe(matched=[(12, "鹽", True, "", "")])  # all staple → denom 0
    assert coverage({12}, r) is None
    r = _recipe()  # empty recipe
    assert coverage({1}, r) is None


def test_ranking_deterministic_and_null_score():
    hi = evaluate({1}, _recipe(id=5, friendly_score=80.0,
                               matched=[(1, "a", False, "", "")],
                               unmatched=["x"]), set(), {})
    lo = evaluate({1}, _recipe(id=6, friendly_score=None,
                               matched=[(1, "a", False, "")],
                               unmatched=["x"]), set(), {})
    rows = sort_recipes([lo, hi])
    assert rows[0]["id"] == 5 and rows[0]["rank_score"] > rows[1]["rank_score"]
    # tie on score → coverage desc → id asc
    a = evaluate({1}, _recipe(id=9, matched=[(1, "a", False, "")]), set(), {})
    b = evaluate({1}, _recipe(id=3, matched=[(1, "a", False, "")]), set(), {})
    assert sort_recipes([a, b])[0]["id"] == 3


def test_hard_exclusion_both_paths_and_staples():
    # allergen via ingredient_allergen on a STAPLE ingredient still excludes
    r = _recipe(matched=[(1, "a", False, ""), (2, "鹽", True, "")],
                allergens={2: "奶"})
    assert evaluate({1}, r, {2}, {}) == {"__excluded__": True}
    # allergen via allergen_hints (name → id map)
    r = _recipe(matched=[(1, "a", False, "")], hints=["蛋"])
    assert evaluate({1}, r, {1}, {"蛋": 1}) == {"__excluded__": True}
    # no exclusion configured → stays
    out = evaluate({1}, r, set(), {"蛋": 1})
    assert out and out["allergens"] == ["蛋"] and out["allergen_warning"]


def test_unknown_hint_warns_but_never_excludes():
    r = _recipe(matched=[(1, "a", False, "")], hints=["不存在的過敏原"])
    out = evaluate({1}, r, {99}, {})
    assert out["unknown_allergen_hints"] == ["不存在的過敏原"]
    assert out["allergen_warning"] is True


def test_selection_warnings():
    sel = [
        SelectedIngredient(1, "蝦", "trigger", "常見誘因", [A_EGG]),
        SelectedIngredient(2, "奶", "caution", "因人而異", [A_MILK]),
        SelectedIngredient(3, "菜", "suitable", "一般適合", []),
        SelectedIngredient(4, "多", "trigger", "常見誘因", [A_EGG, A_MILK]),
    ]
    w = selection_warnings(sel)
    assert {x["ingredient_id"] for x in w} == {1, 2, 4}
    assert w[0]["reasons"] == ["rating_trigger", "has_allergen"]
    assert w[1]["reasons"] == ["has_allergen"]
    assert len(w[2]["allergens"]) == 2


def test_evaluate_fields():
    r = _recipe(
        id=7, matched=[(1, "雞蛋", False, "", ""), (2, "鹽", True, "")],
        unmatched=["怪菜"], hints=["甲殼類"], allergens={3: "蛋"},
        trigger_ingredients=["蝦"], status="pending_review")
    out = evaluate({1, 2}, r, set(), {"甲殼類": 9})
    assert out["matched"] == [
        {"ingredient_id": 1, "name_zh": "雞蛋"},
        {"ingredient_id": 2, "name_zh": "鹽"}]
    assert out["missing"] == ["怪菜"]          # unmatched counts as missing
    assert sorted(out["allergens"]) == ["甲殼類", "蛋"]
    assert out["trigger_ingredients"] == ["蝦"]
    assert out["draft"] is True               # pending_review → draft
    r2 = _recipe(id=7, matched=[(1, "雞蛋", False, "")],
                 unmatched=["u"], status="published")
    assert evaluate({1}, r2, set(), {})["draft"] is True   # unmatched → draft
