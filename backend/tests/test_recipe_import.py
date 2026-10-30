"""Unit tests for app.recipe_import (pure parsing/validation/matching)."""
from app.crawler.matcher import IngredientMatcher
from app.recipe_import import (
    ImportFormatError,
    match_recipes,
    parse_import,
    validate_recipe_form,
)

R_HEADER = "recipe_id,title,description,cook_time_min,servings,steps,tags,notes\n"
I_HEADER = "recipe_id,ingredient_name,qty,unit,note,is_staple\n"


def _recipes(rows):
    return (R_HEADER + "\n".join(rows)).encode()


def _items(rows):
    return (I_HEADER + "\n".join(rows)).encode()


def _ok_pair():
    return _recipes([
        "r1,清炒白菜,簡單,10,2,洗淨||炒熟,快煮,",
        "r2,蒸蛋,,15,2,打散||蒸熟,,",
    ]), _items([
        "r1,白菜,200,克,,N",
        "r1,鹽,,,少許,Y",
        "r2,雞蛋,2,顆,,N",
        "r2,醬油,5,毫升,,N",
    ])


def test_parse_ok():
    res = parse_import(*_ok_pair())
    assert len(res.recipes) == 2 and not res.recipe_errors and not res.errors
    r = res.recipes[0]
    assert r.steps == ["洗淨", "炒熟"] and r.cook_time == 10
    assert r.items[0].qty == 200 and r.items[0].raw_text == "白菜 200克"
    assert r.items[1].is_staple


def test_bom_and_no_bom():
    rb, ib = _ok_pair()
    res = parse_import(b"\xef\xbb\xbf" + rb, ib)
    assert len(res.recipes) == 2


def test_bad_encoding():
    import pytest
    with pytest.raises(ImportFormatError):
        parse_import(b"\xff\xfe bad", b"")


def test_wrong_header():
    import pytest
    with pytest.raises(ImportFormatError):
        parse_import(b"a,b,c\n1,2,3", _items([]))


def test_recipe_id_rules():
    res = parse_import(_recipes([
        "EXAMPLE001,範本,,,,a||b,,",
        "r1,ok,,,,a||b,,",
        "r1,dup,,,,a||b,,",
        "bad id!,x,,,,a||b,,",
    ]), _items(["r1,a,,,,N", "r1,b,,,,N"]))
    keys = {r.external_key for r in res.recipes}
    assert keys == {"r1"}
    assert any("EXAMPLE" in e.message for e in res.errors)
    assert any("重複" in e.message for e in res.errors)


def test_orphan_items_and_min_two():
    res = parse_import(
        _recipes(["r1,x,,,,a||b,,", "r2,y,,,,a||b,,"]),
        _items(["ghost,a,,,,N", "r2,b,,,,N"]))
    assert any("不存在" in e.message for e in res.errors)
    assert res.recipes == []  # r2 has <2 items, ghost rejected r1 has none


def test_forbidden_terms_each():
    from app.admin.rules import RECIPE_FORBIDDEN_TERMS
    for term in RECIPE_FORBIDDEN_TERMS:
        res = parse_import(
            _recipes([f"r1,這道菜{term},,,,a||b,,"]),
            _items(["r1,a,,,,N", "r1,b,,,,N"]))
        assert "r1" in res.recipe_errors, term


def test_tag_prefix_rule():
    for t in ("無過敏原", "不含麩質"):
        res = parse_import(
            _recipes([f"r1,x,,,,a||b,{t},", ]),
            _items(["r1,a,,,,N", "r1,b,,,,N"]))
        assert "r1" in res.recipe_errors, t


def test_limits():
    res = parse_import(
        _recipes(["r1," + "t" * 61 + ",,,,a||b,,",
                  "r2,ok,,601,,a||b,,",
                  "r3,ok,,,21,a||b,,",
                  "r4,ok,,,," + "s" * 301 + "||b,,"]),
        _items(["r2,a,,,,N", "r2,b,,,,N"]))
    assert all(k in res.recipe_errors for k in ("r1", "r2", "r3", "r4"))
    res2 = parse_import(_ok_pair()[0], _items([
        "r1,a,abc,,,N", "r1,b,1,,,,Y", "r2,c,-1,,,N"]))
    assert any("qty" in e.field for e in res2.errors)


def _ctx():
    names = {"雞蛋": 1, "白菜": 2, "鹽": 3, "醬油": 4}
    matcher = IngredientMatcher(names)
    staples = {"鹽", "醬油"}
    kw = {"雞蛋": "蛋", "蛋": "蛋", "醬油": "大豆", "大豆": "大豆"}
    return matcher, staples, kw


def test_matching_and_staples_and_hints():
    res = parse_import(*_ok_pair())
    matcher, staples, kw = _ctx()
    out = match_recipes(res.recipes, matcher, staples, kw)
    r1, r2 = out
    assert set(r1.matched) == {2, 3}
    assert r1.matched[3][0].is_staple  # 鹽 forced staple via list
    assert set(r2.matched) == {1, 4}
    assert "蛋" in r2.allergen_hints and "大豆" in r2.allergen_hints
    # unmatched still scanned
    res2 = parse_import(_recipes(["r5,x,,,,a||b,,"]),
                        _items(["r5,神秘食材,,,,N", "r5,蠔油,,,,N"]))
    kw2 = dict(kw); kw2["蠔油"] = "貝類"
    out2 = match_recipes(res2.recipes, matcher, staples, kw2)[0]
    assert "神秘食材" in out2.unmatched and "蠔油" in out2.unmatched
    assert "貝類" in out2.allergen_hints  # unmatched items still scanned


def test_unmatched_staple_split():
    res = parse_import(_recipes(["r6,x,,,,a||b,,"]),
                       _items(["r6,不知名蔬菜,,,,N", "r6,糖,,,,N"]))
    matcher, staples, kw = _ctx()
    staples = set(staples) | {"糖"}
    out = match_recipes(res.recipes, matcher, staples, kw)[0]
    assert out.unmatched == ["不知名蔬菜"] and out.unmatched_staples == ["糖"]


def test_form_validation():
    parsed, errors = validate_recipe_form(
        title="蒸蛋", description="", cook_raw="15", servings_raw="2",
        steps=["打散", "蒸熟"], tags=["蒸"], notes="",
        items=[{"name": "雞蛋", "qty": "2", "unit": "顆", "note": "", "is_staple": False},
               {"name": "鹽", "qty": "", "unit": "", "note": "少許", "is_staple": True}])
    assert parsed and not errors and len(parsed.items) == 2
    _, errors = validate_recipe_form(
        title="", description="", cook_raw="x", servings_raw="",
        steps=[], tags=[], notes="",
        items=[{"name": "a", "qty": "", "unit": "", "note": "", "is_staple": False}])
    assert errors
