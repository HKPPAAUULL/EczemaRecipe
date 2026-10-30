"""Unit tests for the recipe crawl pipeline (DB-free where possible)."""

from app.crawler.allergens import load_keyword_map, scan_allergens
from app.crawler.base import content_hash, stable_recipe_slug
from app.crawler.matcher import IngredientMatcher
from app.crawler.parse import parse_item, parse_practic
from app.crawler.pipeline import load_staples
from conftest import REPO_ROOT

ALLERGEN_CSV = REPO_ROOT / "data" / "reference" / "allergen_keywords.csv"
STAPLE_CSV = REPO_ROOT / "data" / "reference" / "staple_ingredients.csv"


def test_parse_item_qty_unit_forms():
    assert parse_item("白蘿蔔（客語又叫菜頭）1斤").qty == 1
    assert parse_item("白蘿蔔（客語又叫菜頭）1斤").name == "白蘿蔔"
    assert parse_item("排骨10兩").unit == "兩"
    assert parse_item("香菜少許").qty is None
    assert parse_item("香菜少許").unit == "少許"
    assert parse_item("鹽1/2匙").qty == 0.5
    assert parse_item("梅干菜一把").qty == 1
    assert parse_item("豬肚一副").unit == "副"
    assert parse_item("蒜頭3-5顆").qty is None  # range kept in raw_text
    assert parse_item("過貓300g").qty == 300
    assert parse_item("鮮奶油5c.c").qty == 5
    assert parse_item("香蕉三根").qty == 3
    assert parse_item("大腸").name == "大腸"  # no qty at all


def test_parse_item_halfwidth_and_parens():
    it = parse_item("雞蛋５粒")
    assert it.qty == 5 and it.name == "雞蛋"
    it = parse_item("鳳梨(客語黃梨)2塊")
    assert it.name == "鳳梨" and it.qty == 2


def test_parse_practic_sections():
    text = ("1、材料：白蘿蔔1斤、排骨10兩。2、調味料：鹽少許。"
            "3、步驟：(1)排骨汆燙後同煮30分鐘。")
    r = parse_practic(text)
    assert [i.name for i in r.materials] == ["白蘿蔔", "排骨"]
    assert [i.name for i in r.seasonings] == ["鹽"]
    assert "汆燙" not in str(r.materials)  # steps never parsed into items


def test_parse_practic_empty_seasoning_and_failure():
    r = parse_practic("1、材料：雞蛋1顆、牛奶130毫升。2、調味料：3、步驟：(1)混合")
    assert r is not None and r.seasonings == []
    assert parse_practic("完全沒有標記的文字") is None


def test_matcher_exact_and_longest_token():
    m = IngredientMatcher.from_rows([
        (1, "雞胸肉", ["雞胸"]),
        (2, "紅蘿蔔", ["胡蘿蔔"]),
        (3, "雞蛋", ["蛋"]),
        (4, "番茄", ["蕃茄"]),
    ])
    assert m.match("雞胸肉") == 1
    assert m.match("去皮雞胸肉") == 1      # longest token hit
    assert m.match("紅蘿蔔絲") == 2
    assert m.match("柳丁") is None         # no hit


def test_matcher_ambiguous_returns_none():
    m = IngredientMatcher.from_rows([
        (1, "雞蛋", []), (2, "番茄", ["蕃茄"]), (3, "柳丁", []),
    ])
    # "柳丁及蕃茄各1個" contains both 柳丁 and 蕃茄 → 不同食材同長 → 歧義
    assert m.match("柳丁及蕃茄各1個(盤飾用)") is None
    # single hit still matches when lengths differ
    assert m.match("牛蕃茄一粒") == 2


def test_allergen_hidden_forms_and_unmatched_items():
    kw = load_keyword_map(ALLERGEN_CSV)
    hits = scan_allergens(["蠔油10克", "美乃滋1包", "鹽少許"], kw)
    assert "甲殼類" in hits and "蛋" in hits
    assert "鹽" not in hits
    # unmatched 原文 still scanned
    hits = scan_allergens(["某不知名芝士材料"], kw)
    assert "奶" in hits  # 芝士 hidden form
    assert scan_allergens([], kw) == []
    assert scan_allergens(["", "  "], kw) == []


def test_staple_list():
    staples = load_staples(STAPLE_CSV)
    assert "鹽" in staples and "太白粉" in staples and "醬油" in staples
    assert "雞蛋" not in staples


def test_content_hash_stable_and_slug_unique():
    h1 = content_hash("a", "b")
    assert h1 == content_hash("a", "b") != content_hash("a", "c")
    assert stable_recipe_slug("排骨炆菜頭") != stable_recipe_slug("酸菜炆豬肚")
    assert stable_recipe_slug("x").startswith("r-")


# --------------------------------------------------------------------------
# pipeline import against a fake connection (no psycopg, no DB)
# --------------------------------------------------------------------------


class FakeResult:
    def __init__(self, rows=(), rowcount=1):
        self._rows = list(rows)
        self.rowcount = rowcount

    def __iter__(self):
        return iter(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeConn:
    def __init__(self, ingredients, existing=None):
        self.ingredients = ingredients  # [(id, name, aliases)]
        self.existing = existing or {}  # source_url -> (id, status, hash)
        self.queries = []
        self._next = 1

    def execute(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        self.queries.append(s)
        if s.startswith("select id, name_zh, aliases from ingredient"):
            return FakeResult(self.ingredients)
        if s.startswith("select id from data_source"):
            return FakeResult([(9,)])
        if s.startswith("select id, status, content_hash from recipe"):
            row = self.existing.get(params[0])
            return FakeResult([row] if row else [])
        if "returning id" in s:
            self._next += 1
            return FakeResult([(self._next,)])
        return FakeResult()


def _rec(unmatched_name="未識別"):
    from app.crawler.hakka import RecipeRecord
    from app.crawler.parse import ParsedItem

    return RecipeRecord(
        title="測試菜", description="經典；炆",
        source_url="https://data.gov.tw/dataset/147690#r-test",
        tags=["經典", "炆"], content_hash=content_hash("測試菜"),
        items=[ParsedItem("雞胸肉100g", "雞胸肉", 100, "g"),
               ParsedItem(f"{unmatched_name}10g", unmatched_name, 10, "g")],
        seasoning_items=[ParsedItem("鹽少許", "鹽", None, "少許")],
    )


def test_import_never_overwrites_manual_status():
    from app.crawler.pipeline import import_recipes

    rec = _rec()
    conn = FakeConn(
        [(1, "雞胸肉", []), (2, "鹽", [])],
        existing={rec.source_url: (7, "published", "oldhash")},
    )
    stats = import_recipes(conn, "s", "u", "l", [rec],
                           keyword_map={}, staples=set())
    assert stats.skipped_manual_status == 1
    assert not any(
        q.startswith(("update recipe", "insert into recipe "))
        for q in conn.queries
    )


def test_import_skips_unchanged_hash():
    from app.crawler.pipeline import import_recipes

    rec = _rec()
    conn = FakeConn(
        [(1, "雞胸肉", []), (2, "鹽", [])],
        existing={rec.source_url: (7, "pending_review", rec.content_hash)},
    )
    stats = import_recipes(conn, "s", "u", "l", [rec],
                           keyword_map={}, staples=set())
    assert stats.skipped_unchanged == 1
    assert not any(
        q.startswith(("insert into recipe ", "update recipe"))
        for q in conn.queries
    )


def test_import_writes_pending_review_and_queue():
    from app.crawler.pipeline import import_recipes

    conn = FakeConn([(1, "雞胸肉", []), (2, "鹽", [])])
    stats = import_recipes(conn, "s", "u", "l", [_rec()],
                           keyword_map={"蠔油": "甲殼類"}, staples={"鹽"})
    assert stats.inserted == 1 and stats.unmatched_items == 1
    ins = [q for q in conn.queries if q.startswith("insert into recipe ")]
    assert ins and "'pending_review'" in ins[0]
    assert "published" not in ins[0].split("pending_review")[0].replace(
        "'pending_review'", "")
    assert any(q.startswith("insert into review_queue") for q in conn.queries)


def test_parse_item_qty_first_form():
    it = parse_item("1/2醋匙")
    assert (it.name, it.qty, it.unit) == ("醋", 0.5, "匙")
    it = parse_item("3根香蕉")
    assert it.name == "香蕉" and it.qty == 3


def test_parse_item_compound_and_mojibake():
    it = parse_item("九層塔20克")
    assert (it.name, it.qty, it.unit) == ("九層塔", 20, "克")
    it = parse_item("四季豆200g")
    assert (it.name, it.qty) == ("四季豆", 200)
    it = parse_item("木?子葉20g")  # 亂碼原樣保留 → 不配對
    assert "?" in it.name


def test_unmatched_staple_goes_to_own_column_and_hints_still_scan():
    """醬油 unmatched→unmatched_staples，但 allergen_hints 仍含大豆。"""
    from app.crawler.hakka import RecipeRecord
    from app.crawler.parse import ParsedItem
    from app.crawler.pipeline import import_recipes

    rec = RecipeRecord(
        title="測試菜", description="", source_url="https://x#r-1",
        tags=[], content_hash=content_hash("測試菜"),
        items=[ParsedItem("雞胸肉100g", "雞胸肉", 100, "g")],
        seasoning_items=[ParsedItem("醬油1大匙", "醬油", 1, "大匙")],
    )
    conn = FakeConn([(1, "雞胸肉", [])])
    captured = {}

    orig = FakeConn.execute

    def spy(self, sql, params=None):
        s = " ".join(str(sql).split()).lower()
        if s.startswith("insert into recipe ") and params:
            captured["params"] = params
        return orig(self, sql, params)

    import types
    conn.execute = types.MethodType(spy, conn)
    stats = import_recipes(conn, "s", "u", "l", [rec],
                           keyword_map={"醬油": "大豆"}, staples={"醬油"})
    assert stats.unmatched_items == 0 and stats.unmatched_staples == 1
    params = captured["params"]
    assert params[5] == []               # unmatched_ingredients empty
    assert params[6] == ["醬油1大匙"]     # unmatched_staples
    assert params[7] == ["大豆"]          # allergen_hints still hit
