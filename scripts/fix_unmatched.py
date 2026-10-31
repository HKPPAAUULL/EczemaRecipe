"""One-off: resolve crawled recipes' unmatched ingredients in bulk.

Creates draft ingredients / maps synonyms / ignores non-food via the
admin repository functions so audit + queue notes stay intact.
Run with DATABASE_URL set, from backend/ with the project venv.
"""

import os
import sys

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.admin import repository as repo

# kind: "new" → (canonical, category_id, is_staple, extra_aliases)
#       "map" → (target_name, is_staple, extra_aliases_to_add)
#       "ignore" → reason
ACTIONS = {
    # 辣椒 family
    "辣椒1支": ("new", "辣椒", 3, False, ["紅辣椒", "辣椒末", "辣椒碎", "辣椒絲", "乾辣椒", "乾辣椒段"]),
    "乾辣椒段10g": ("map", "辣椒", False, []),
    "紅辣椒1支": ("map", "辣椒", False, []),
    "紅辣椒兩根": ("map", "辣椒", False, []),
    "辣椒10g": ("map", "辣椒", False, []),
    "辣椒1條": ("map", "辣椒", False, []),
    "辣椒少許": ("map", "辣椒", False, []),
    "辣椒末3粒": ("map", "辣椒", False, []),
    "辣椒碎1支": ("map", "辣椒", False, []),
    "辣椒絲1支": ("map", "辣椒", False, []),
    # 蔬菜/香草
    "九層塔20克": ("new", "九層塔", 3, False, ["羅勒", "金不換"]),
    "九層塔適量": ("map", "九層塔", False, []),
    "仙草300g": ("new", "仙草", 12, False, ["涼粉草"]),
    "四季豆200g": ("new", "四季豆", 3, False, ["敏豆", "菜豆"]),
    "大頭菜1粒": ("new", "大頭菜", 3, False, ["結頭菜"]),
    "孛齊100克": ("new", "荸薺", 3, False, ["孛齊", "馬蹄"]),
    "客家酸菜5兩": ("new", "酸菜", 3, False, ["客家酸菜"]),
    "鹹菜半斤": ("new", "鹹菜", 3, False, []),
    "梅乾菜2兩半": ("new", "梅乾菜", 3, False, ["梅干菜"]),
    "梅干菜一把": ("map", "梅乾菜", False, []),
    "福菜4兩": ("new", "福菜", 3, False, []),
    "筍乾1斤": ("new", "筍乾", 3, False, []),
    "桶筍半支": ("new", "竹筍", 3, False, ["筍", "鮮筍", "桶筍", "筍絲"]),
    "筍絲38g": ("map", "竹筍", False, []),
    "秋葵10支": ("new", "秋葵", 3, False, []),
    "秋葵5支": ("map", "秋葵", False, []),
    "野蓮1包": ("new", "野蓮", 3, False, []),
    "過貓300g": ("new", "過貓", 3, False, ["過貓菜", "過溝菜蕨"]),
    "過貓菜300克": ("map", "過貓", False, []),
    "紫蘇葉十片": ("new", "紫蘇", 3, False, ["紫蘇葉"]),
    "艾草心2斤": ("new", "艾草", 3, False, ["艾草心"]),
    "木?子1/4個": ("new", "木鱉子", 4, False, ["木虌子", "木鳖子", "木?子", "木?子葉"]),
    "木?子葉20g": ("map", "木鱉子", False, []),
    "長豆(或翼豆)100g": ("new", "長豆", 3, False, ["豇豆", "長豇豆", "翼豆"]),
    "長豇豆50克": ("map", "長豆", False, []),
    "長豆乾": ("new", "長豆乾", 3, False, []),
    "紅蔥頭1兩": ("new", "紅蔥頭", 3, False, ["紅蔥酥", "乾蔥頭"]),
    "紅蔥頭2兩": ("map", "紅蔥頭", False, []),
    "紅蔥頭30g": ("map", "紅蔥頭", False, []),
    "紅蔥頭5粒": ("map", "紅蔥頭", False, []),
    "紅蔥頭片38g": ("map", "紅蔥頭", False, []),
    "紅蔥酥(帶油的)適量": ("map", "紅蔥頭", False, ["紅蔥酥"]),
    "香菜1小撮": ("map", "香菜", False, []),
    "香菜少許": ("map", "香菜", False, []),
    # 肉類/海鮮
    "豬肚1個": ("new", "豬肚", 1, False, []),
    "豬肚一副": ("map", "豬肚", False, []),
    "豬肺4兩": ("new", "豬肺", 1, False, []),
    "大腸": ("new", "豬大腸", 1, False, ["大腸", "豬腸"]),
    "豬大腸半斤": ("map", "豬大腸", False, []),
    "絞肉4兩": ("new", "免治豬肉", 1, False, ["絞肉", "豬絞肉", "肉碎", "豬肉碎", "免治肉"]),
    "絞肉6兩": ("map", "免治豬肉", False, []),
    "豬絞肉1斤": ("map", "免治豬肉", False, []),
    "豬絞肉250克": ("map", "免治豬肉", False, []),
    "豬絞肉300克": ("map", "免治豬肉", False, []),
    "鹹豬肉30g": ("new", "鹹豬肉", 1, False, []),
    "土雞塊300g": ("new", "土雞", 1, False, ["土雞塊", "放山雞"]),
    "無頭鴨(先滷好)半隻": ("new", "鴨肉", 1, False, ["鴨", "無頭鴨"]),
    "鴨紅6兩": ("new", "鴨血", 1, False, ["鴨紅"]),
    "蛤蠣8顆": ("map", "蜆", False, ["蛤蠣"]),
    "小魚乾5g": ("new", "小魚乾", 2, False, ["丁香魚", "小魚干"]),
    # 蛋奶/穀物
    "吐司10g": ("map", "白麵包", False, ["吐司"]),
    "天使麵200g": ("map", "小麥麵條", False, ["天使麵"]),
    "春捲皮10張": ("new", "春捲皮", 5, False, ["春卷皮"]),
    "鮮奶油5c.c": ("new", "鮮奶油", 6, False, ["淡奶油", "忌廉"]),
    # 豆製品
    "豆干30g": ("new", "豆干", 7, False, ["豆乾"]),
    "豆干5塊": ("map", "豆干", False, []),
    "豆鼓10克": ("map", "豆豉", True, ["豆鼓"]),
    # 調味料/常備料 (is_staple)
    "美乃滋1包": ("new", "美乃滋", 9, True, ["蛋黃醬", "沙拉醬"]),
    "桔醬20克": ("new", "桔醬", 9, True, ["金桔醬", "金橘醬"]),
    "金桔醬": ("map", "桔醬", True, []),
    "樹子醬2兩": ("new", "樹子醬", 9, True, ["樹子", "破布子"]),
    "辣味露1茶匙": ("new", "辣味露", 9, True, ["辣椒水"]),
    "鮮味露2茶匙": ("new", "鮮味露", 9, True, []),
    "醋精少許": ("map", "白醋", True, ["醋精"]),
    "雞高湯200c.c": ("new", "雞高湯", 12, True, ["高湯", "上湯"]),
    "吉士粉": ("new", "吉士粉", 12, True, ["卡士達粉"]),
    "蘇打粉8克": ("new", "蘇打粉", 12, True, ["梳打粉", "小蘇打", "小蘇打粉"]),
    "酥炸粉": ("new", "酥炸粉", 12, True, ["炸粉"]),
    # 水果/其他
    "金桔3顆": ("new", "金桔", 4, False, ["金橘"]),
    "蓮霧2粒": ("new", "蓮霧", 4, False, []),
    "柿餅3兩": ("new", "柿餅", 4, False, []),
    "枸杞10克": ("new", "枸杞", 12, False, ["枸杞子"]),
    # 無法確定/非食材
    "柳丁及蕃茄各1個(盤飾用)": ("ignore", "盤飾用混合食材，非單一食材"),
    "翡翠60克": ("ignore", "名稱含糊（翡翠），未能確定為哪種食材"),
}


def iid_of(conn, name):
    r = conn.execute("SELECT id FROM ingredient WHERE name_zh = %s", (name,)).fetchone()
    return r["id"] if r else None


def add_aliases(conn, iid, aliases):
    for a in aliases:
        conn.execute(
            "UPDATE ingredient SET aliases = array_append(aliases, %s)"
            " WHERE id = %s AND NOT (%s = ANY(aliases))",
            (a, iid, a),
        )


def main():
    stats = {"new": 0, "map": 0, "ignore": 0, "fail": 0, "unhandled": []}
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        recs = conn.execute(
            "SELECT id, unmatched_ingredients FROM recipe"
            " WHERE cardinality(unmatched_ingredients) > 0 ORDER BY id"
        ).fetchall()
        for rec in recs:
            rid, items = rec["id"], rec["unmatched_ingredients"]
            for item in list(items):
                spec = ACTIONS.get(item)
                if spec is None:
                    stats["unhandled"].append((rid, item))
                    continue
                kind = spec[0]
                if kind == "ignore":
                    errs = repo.ignore_unmatched(conn, rid, item, spec[1])
                    key = "ignore"
                elif kind == "map":
                    tgt = iid_of(conn, spec[1])
                    if tgt is None:
                        errs = [f"target {spec[1]} missing"]
                    else:
                        if spec[3]:
                            add_aliases(conn, tgt, spec[3])
                        errs = repo.map_unmatched(conn, rid, item, tgt, spec[2])
                    key = "map"
                else:  # new
                    canonical, cat, staple, extra = spec[1:]
                    tgt = iid_of(conn, canonical)
                    if tgt is None:
                        errs = repo.create_ingredient_for_unmatched(
                            conn, rid, item, canonical, cat, staple)
                        if not errs:
                            tgt = iid_of(conn, canonical)
                            add_aliases(conn, tgt, extra)
                        key = "new"
                    else:  # already created earlier in this run
                        if extra:
                            add_aliases(conn, tgt, extra)
                        errs = repo.map_unmatched(conn, rid, item, tgt, staple)
                        key = "map"
                if errs:
                    stats["fail"] += 1
                    print(f"FAIL rid={rid} item={item}: {errs}")
                else:
                    stats[key] += 1
        conn.commit()
    print({k: v for k, v in stats.items() if k != "unhandled"})
    for rid, item in stats["unhandled"]:
        print(f"UNHANDLED rid={rid} {item}")


if __name__ == "__main__":
    main()
