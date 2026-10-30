"""Unit tests for the TFDA nutrition pipeline (DB-free).

Small inline fixtures exercise normalization, the raw/processed rule, the
tiered exact-match rules, nutrient whitelisting/units and reference-CSV
validation. import_nutrition is tested against a FakeConn so we can assert
it never inserts into `ingredient` or touches `reviewed`.
"""

import re
import textwrap

import pytest

from app.nutrition import (
    NUTRIENT_ORDER,
    NUTRIENT_WHITELIST,
    NutritionValidationError,
    ReferenceRow,
    TfdaSample,
    build_name_indexes,
    build_reference_rows,
    import_nutrition,
    is_unprocessed,
    load_tfda_samples,
    match_ingredient,
    match_keys,
    normalize_text,
    normalize_unit,
    parse_amount,
    parse_reference_csv,
)

RAW_HEADER = (
    "食品分類,資料類別,整合編號,樣品名稱,俗名,樣品英文名稱,內容物描述,"
    "廢棄率,分析項分類,分析項,含量單位,每100克含量,樣本數,標準差,"
    "每單位含量,每單位重,每單位重含量"
)


def raw_line(iid, name, common, desc, cat="蔬菜類", dtype="樣品基本資料",
             item="熱量", unit="kcal", amount="10"):
    return (
        f"{cat},{dtype},{iid},{name},{common},,{desc},0,一般成分,"
        f"{item},{unit},{amount},,,,0.0克,"
    )


def write_raw(tmp_path, body):
    p = tmp_path / "raw.csv"
    p.write_text(
        RAW_HEADER + "\n" + textwrap.dedent(body), encoding="utf-8"
    )
    return p


def make_sample(iid="A1", name="白菜", cat="蔬菜類", state="生",
                desc="樣品狀態:生", common="", nutrients=None):
    keys = match_keys(name)
    ckeys = set()
    for a in common.split(","):
        if a.strip():
            ckeys |= match_keys(a)
    return TfdaSample(
        integration_id=iid, sample_name=name, food_category=cat,
        sample_state=state, description=desc, name_keys=keys,
        common_keys=ckeys, nutrients=nutrients or {},
    )


def indexes(*samples):
    return build_name_indexes({s.integration_id: s for s in samples})


# ---------------------------------------------------------------------------
# normalization / parsing helpers
# ---------------------------------------------------------------------------


def test_normalize_text_fullwidth_and_spaces():
    assert normalize_text(" ＡＢ１２３ 雞　蛋 ") == "AB123雞蛋"
    assert normalize_text("ａｌｐｈａ") == "alpha"
    assert normalize_text("") == ""


def test_match_keys_strips_parens_and_average_suffix():
    keys = match_keys("雞蛋(白殼)")
    assert {"雞蛋(白殼)", "雞蛋"} <= keys
    keys = match_keys("雞蛋平均值")
    assert {"雞蛋平均值", "雞蛋"} <= keys
    assert match_keys("") == set()


def test_parse_amount():
    assert parse_amount("  117 ") == 117.0
    assert parse_amount("0") == 0.0
    assert parse_amount("") is None
    assert parse_amount("1.00/1.85/1.25") is None  # 比例字串略過
    assert parse_amount("微量") is None
    assert parse_amount("-1") is None


def test_normalize_unit():
    assert normalize_unit("ug") == "µg"
    assert normalize_unit("I.U.") == "IU"
    assert normalize_unit("mg") == "mg"


# ---------------------------------------------------------------------------
# raw / processed rule
# ---------------------------------------------------------------------------


def test_unprocessed_raw_states():
    assert is_unprocessed(make_sample(state="生")) is True
    assert is_unprocessed(make_sample(state="生,冷凍包裝")) is True
    assert is_unprocessed(
        make_sample(state="生,雞胸部位", cat="肉類")
    ) is True


def test_unprocessed_excludes_processed_states():
    for state in ["熟", "乾貨", "醃漬品", "熟,冷凍包裝", "雞蛋製品(雞蛋,鹽)"]:
        assert is_unprocessed(make_sample(state=state)) is False, state


def test_unprocessed_excludes_processed_categories():
    for cat in ["加工調理食品及其他類", "糕餅點心類", "飲料類", "糖類"]:
        assert is_unprocessed(make_sample(cat=cat)) is False, cat
    # 糖類蜂蜜即使樣品狀態非加工也排除
    assert is_unprocessed(
        make_sample(cat="糖類", state="冬蜜", name="蜂蜜(冬蜜)")
    ) is False


def test_unprocessed_missing_state_falls_back_to_description():
    assert is_unprocessed(
        make_sample(state="", desc="前處理描述:混合均勻打碎")
    ) is True
    assert is_unprocessed(
        make_sample(state="", desc="前處理描述:以水煮熟")
    ) is False
    assert is_unprocessed(
        make_sample(state="", desc="前處理描述:醃漬後混合")
    ) is False


def test_unprocessed_excludes_powder_and_processed_names():
    assert is_unprocessed(
        make_sample(name="黑豆粉", cat="豆類", state="",
                    desc="前處理描述:混合均勻")
    ) is False
    assert is_unprocessed(
        make_sample(name="鹽酥花生(熟)", cat="堅果及種子類", state="",
                    desc="前處理描述:混合")
    ) is False


# ---------------------------------------------------------------------------
# matching tiers
# ---------------------------------------------------------------------------


def test_match_exact_name_unique():
    s = make_sample(iid="E1", name="冬瓜")
    name_idx, common_idx = indexes(s)
    samples = {"E1": s}
    m = match_ingredient("冬瓜", [], name_idx, common_idx, samples)
    assert m.status == "matched" and m.via == "name"
    assert m.sample.integration_id == "E1"


def test_match_no_candidate():
    s = make_sample(iid="E1", name="冬瓜")
    name_idx, common_idx = indexes(s)
    m = match_ingredient("不存在", ["沒有"], name_idx, common_idx, {"E1": s})
    assert m.status == "no_candidate"


def test_match_prefers_name_tier_over_alias_false_positive():
    # 雞子 是雞蛋的別名，但 雞睪丸 俗名也有 雞子 → 不得因別名誤配雞睪丸
    testis = make_sample(
        iid="I1", name="雞睪丸", cat="肉類",
        state="生,雞臟器", desc="樣品狀態:生,雞臟器", common="雞子,雞佛",
    )
    egg_avg = make_sample(iid="K1", name="雞蛋平均值", cat="蛋類")
    egg_white = make_sample(iid="K2", name="雞蛋(白殼)", cat="蛋類")
    name_idx, common_idx = indexes(testis, egg_avg, egg_white)
    samples = {s.integration_id: s for s in (testis, egg_avg, egg_white)}
    m = match_ingredient("雞蛋", ["雞子"], name_idx, common_idx, samples)
    # name 層有兩個合格候選（白殼蛋+平均值）→ 取唯一平均值
    assert m.status == "matched_avg"
    assert m.sample.integration_id == "K1"


def test_match_unique_average_resolves_ambiguity():
    a = make_sample(iid="L1", name="全脂鮮乳平均值", cat="乳品類",
                    state="全脂鮮乳", common="牛奶")
    b = make_sample(iid="L2", name="低脂鮮乳", cat="乳品類",
                    state="低脂鮮乳", common="牛奶")
    name_idx, common_idx = indexes(a, b)
    m = match_ingredient(
        "牛奶", [], name_idx, common_idx,
        {"L1": a, "L2": b},
    )
    assert m.status == "matched_avg" and m.via == "alias"
    assert m.sample.integration_id == "L1"


def test_match_ambiguous_skips():
    a = make_sample(iid="D1", name="西瓜平均值(紅肉)", cat="水果類",
                    state="紅肉")
    b = make_sample(iid="D2", name="西瓜平均值(黃肉)", cat="水果類",
                    state="黃肉")
    name_idx, common_idx = indexes(a, b)
    m = match_ingredient("西瓜", [], name_idx, common_idx, {"D1": a, "D2": b})
    assert m.status == "ambiguous" and m.sample is None
    assert len(m.candidates) == 2


def test_match_all_processed_skips():
    a = make_sample(iid="R1", name="醃漬花生仁", cat="加工調理食品及其他類",
                    state="醃漬品", common="花生")
    name_idx, common_idx = indexes(a)
    m = match_ingredient("花生", [], name_idx, common_idx, {"R1": a})
    assert m.status == "no_eligible" and m.sample is None
    assert m.candidates[0].integration_id == "R1"


def test_match_alias_via_sample_name_and_common():
    via_name = make_sample(iid="J1", name="草魚(含皮)", cat="魚貝類")
    via_common = make_sample(iid="J2", name="菲律賓簾蛤", cat="魚貝類",
                             common="花蛤")
    name_idx, common_idx = indexes(via_name, via_common)
    samples = {"J1": via_name, "J2": via_common}
    m = match_ingredient("鯇魚", ["草魚"], name_idx, common_idx, samples)
    assert m.status == "matched" and m.sample.integration_id == "J1"
    m = match_ingredient("蜆", ["花蛤"], name_idx, common_idx, samples)
    assert m.status == "matched" and m.sample.integration_id == "J2"


# ---------------------------------------------------------------------------
# nutrient extraction
# ---------------------------------------------------------------------------


def test_load_samples_whitelist_units_and_values(tmp_path):
    p = write_raw(tmp_path, """\
        蔬菜類,樣品基本資料,E1,白菜,,,樣品狀態:生,0,一般成分,熱量,kcal,               12,,,,0.0克,
        蔬菜類,樣品基本資料,E1,白菜,,,樣品狀態:生,0,礦物質,鈉,mg,               5.5,,,,0.0克,
        蔬菜類,樣品基本資料,E1,白菜,,,樣品狀態:生,0,礦物質,鈣,mg,,,,,0.0克,
        蔬菜類,樣品基本資料,E1,白菜,,,樣品狀態:生,0,其他,P/M/S,,1.00/1.85/1.25,,,,0.0克,
        蔬菜類,樣品基本資料,E1,白菜,,,樣品狀態:生,0,維生素D,維生素D總量(ug),ug,               0.5,,,,0.0克,
        蔬菜類,樣品基本資料,E1,白菜,,,樣品狀態:生,0,礦物質,鈉,g,               9,,,,0.0克,
    """)
    samples = load_tfda_samples(p)
    s = samples["E1"]
    assert s.nutrients["熱量"] == (1, "熱量", "kcal", 12.0)
    assert s.nutrients["鈉"] == (1, "鈉", "mg", 5.5)
    assert s.nutrients["維生素D"] == (1, "維生素D", "µg", 0.5)
    assert "鈣" not in s.nutrients  # 空值略過
    assert "P/M/S" not in s.nutrients  # 不在白名單


def test_load_samples_prefers_average_rows(tmp_path):
    p = write_raw(tmp_path, """\
        蔬菜類,樣品基本資料,E1,白菜平均值,,,樣品狀態:生,0,一般成分,熱量,kcal,10,,,,0.0克,
        蔬菜類,樣品平均值,E1,白菜平均值,,,樣品狀態:生,0,一般成分,熱量,kcal,20,,,,0.0克,
    """)
    s = load_tfda_samples(p)["E1"]
    assert s.nutrients["熱量"] == (0, "熱量", "kcal", 20.0)
    assert s.is_average


def test_build_reference_rows(tmp_path):
    p = write_raw(tmp_path, """\
        蔬菜類,樣品基本資料,E1,冬瓜,,,樣品狀態:生,0,一般成分,熱量,kcal,11,,,,0.0克,
        蔬菜類,樣品基本資料,E1,冬瓜,,,樣品狀態:生,0,礦物質,鋅,mg,0.1,,,,0.0克,
    """)
    samples = load_tfda_samples(p)
    name_idx, common_idx = build_name_indexes(samples)
    m = match_ingredient("冬瓜", [], name_idx, common_idx, samples)
    rows = build_reference_rows([m])
    assert [(r.nutrient_name, r.unit, r.amount_per_100g) for r in rows] == [
        ("熱量", "kcal", 11.0), ("鋅", "mg", 0.1),
    ]
    assert rows[0].tfda_sample_name == "冬瓜"


def test_whitelist_is_gmgugkcal_only():
    assert {u for _, u in NUTRIENT_WHITELIST.values()} <= {
        "g", "mg", "µg", "kcal"
    }
    assert len(NUTRIENT_ORDER) == len(set(NUTRIENT_ORDER))
    assert set(NUTRIENT_ORDER) == {n for n, _ in NUTRIENT_WHITELIST.values()}


# ---------------------------------------------------------------------------
# reference CSV validation
# ---------------------------------------------------------------------------

REF_HEADER = (
    "ingredient_name_zh,tfda_integration_id,tfda_sample_name,"
    "nutrient_name,unit,amount_per_100g"
)


def write_ref(tmp_path, body):
    p = tmp_path / "ref.csv"
    p.write_text(REF_HEADER + "\n" + textwrap.dedent(body), encoding="utf-8")
    return p


def test_parse_reference_csv_ok(tmp_path):
    p = write_ref(tmp_path, "冬瓜,E1,冬瓜平均值,熱量,kcal,11.0\n"
                            "冬瓜,E1,冬瓜平均值,鈉,mg,2.0")
    rows = parse_reference_csv(p)
    assert len(rows) == 2 and rows[0].nutrient_name == "熱量"


@pytest.mark.parametrize(
    "line",
    [
        "冬瓜,E1,冬瓜平均值,熱量,IU,11.0",   # 非法單位
        "冬瓜,E1,冬瓜平均值,熱量,kcal,微量",  # 非數字
        "冬瓜,E1,冬瓜平均值,熱量,kcal,-1",   # 負數
        ",E1,冬瓜平均值,熱量,kcal,11.0",     # 空食材名
    ],
)
def test_parse_reference_csv_rejects_bad_rows(tmp_path, line):
    p = write_ref(tmp_path, line)
    with pytest.raises(NutritionValidationError, match="row 2"):
        parse_reference_csv(p)


def test_parse_reference_csv_rejects_duplicates(tmp_path):
    p = write_ref(tmp_path, "冬瓜,E1,X,熱量,kcal,1\n冬瓜,E2,Y,熱量,kcal,2")
    with pytest.raises(NutritionValidationError, match="duplicate"):
        parse_reference_csv(p)


def test_parse_reference_csv_rejects_empty(tmp_path):
    p = write_ref(tmp_path, "")
    with pytest.raises(NutritionValidationError):
        parse_reference_csv(p)


# ---------------------------------------------------------------------------
# import_nutrition against a fake connection (no psycopg, no DB)
# ---------------------------------------------------------------------------


class FakeResult:
    def __init__(self, rows=(), rowcount=1):
        self._rows = list(rows)
        self.rowcount = rowcount

    def __iter__(self):
        return iter(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    def __init__(self, ingredients):
        self.ingredients = dict(ingredients)  # name_zh -> id
        self.queries = []
        self._next = 50

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        self.queries.append(s)
        if s.startswith("select id, name_zh from ingredient"):
            return FakeResult(
                [(iid, name) for name, iid in self.ingredients.items()]
            )
        if s.startswith("select id from data_source where name"):
            return FakeResult([(7,)])
        if s.startswith("select id from nutrient"):
            return FakeResult([(params and 3 or 3,)])
        if "returning id" in s:
            self._next += 1
            return FakeResult([(self._next,)])
        return FakeResult()


def _ref(name="冬瓜", nutrient="熱量", unit="kcal", amount=11.0):
    return ReferenceRow(name, "E1", "冬瓜平均值", nutrient, unit, amount)


def test_import_never_inserts_or_modifies_ingredient():
    conn = FakeConn({"冬瓜": 9})
    summary = import_nutrition(conn, [_ref()])
    assert summary.values_written == 1
    assert summary.ingredients_matched == 1
    dml = [q for q in conn.queries if q.startswith(("insert", "update"))]
    for q in dml:
        assert "insert into ingredient " not in q
        assert "update ingredient " not in q
        assert not re.search(r"\breviewed(_at)?\b", q), q
    # upsert 語法：PK 衝突更新數值，重跑不重複
    ins = [q for q in conn.queries if "insert into ingredient_nutrient" in q]
    assert ins and "on conflict" in ins[0] and "source_id" in ins[0]


def test_import_skips_missing_ingredients():
    conn = FakeConn({"冬瓜": 9})
    summary = import_nutrition(
        conn, [_ref("不存在", "鈉", "mg", 2.0), _ref("冬瓜")]
    )
    assert summary.ingredients_missing == 1
    assert summary.missing_names == ["不存在"]
    assert summary.values_written == 1


def test_import_upserts_tfda_source_once():
    conn = FakeConn({"冬瓜": 9})
    import_nutrition(conn, [_ref()])
    upserts = [
        q for q in conn.queries
        if "data_source" in q and q.startswith(("insert", "update"))
    ]
    assert len(upserts) == 1 and upserts[0].startswith("update")
