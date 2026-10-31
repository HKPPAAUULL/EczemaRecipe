"""One-off: propose ratings for the quick-added draft ingredients.

Sets eczema_rating/rating_reason/needs_senior_review, links allergens
and evidence via admin repository helpers (audit rows preserved).
Ingredients stay unreviewed — human review still required.
Run with DATABASE_URL set.
"""

import os
import sys

import psycopg
from psycopg.rows import dict_row

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from app.admin import repository as repo

STD = "非常見過敏原；一般適合日常食用，個別人士仍可能過敏"
HIST = ("{note}組織胺或較高，建議少量（依據：組織胺；適用：已知組織胺不耐受者"
        "（證據有限，不建議盲目戒口）；來源：組織胺不耐受綜述（PMC））")
ALLERGEN = ("{what}為常見食物過敏原之一；已確診{who}者須避免，其他人可在觀察下少量嘗試"
            "（依據：過敏原；來源：食安中心）")

CFS = ("www.cfs.gov.hk/english/consumer_zone/safefood_all/food_allergy.html",
       "https://www.cfs.gov.hk/english/consumer_zone/safefood_all/food_allergy.html")
PMC = ("pmc.ncbi.nlm.nih.gov/articles/PMC7463562",
       "https://pmc.ncbi.nlm.nih.gov/articles/PMC7463562/")
SWAIN = ("pubmed.ncbi.nlm.nih.gov/4019987", "https://pubmed.ncbi.nlm.nih.gov/4019987")
POLLEN = ("www.annallergy.org/article/S1081-1206%2819%2930540-X/fulltext",
          "https://www.annallergy.org/article/S1081-1206%2819%2930540-X/fulltext")
GOJI = ("pubmed.ncbi.nlm.nih.gov/23101309", "https://pubmed.ncbi.nlm.nih.gov/23101309/")

# name: (rating, reason, senior, [allergen_types], [evidence])
PLAN = {
    # 一般適合（非常見過敏原）
    "豬肚": ("suitable", STD, False, [], []),
    "豬肺": ("suitable", STD, False, [], []),
    "豬大腸": ("suitable", STD, False, [], []),
    "免治豬肉": ("suitable", STD, False, [], []),
    "土雞": ("suitable", STD, False, [], []),
    "鴨肉": ("suitable", STD, False, [], []),
    "鴨血": ("suitable", STD, False, [], []),
    "秋葵": ("suitable", STD, False, [], []),
    "四季豆": ("suitable", STD, False, [], []),
    "竹筍": ("suitable", STD, False, [], []),
    "荸薺": ("suitable", STD, False, [], []),
    "野蓮": ("suitable", STD, False, [], []),
    "過貓": ("suitable", STD, False, [], []),
    "大頭菜": ("suitable", STD, False, [], []),
    "紅蔥頭": ("suitable", STD, False, [], []),
    "九層塔": ("suitable", STD, False, [], []),
    "紫蘇": ("suitable", STD, False, [], []),
    "長豆": ("suitable", STD, False, [], []),
    "蓮霧": ("suitable", STD, False, [], []),
    "蘇打粉": ("suitable", "非過敏原；一般適合", False, [], []),
    # 九大過敏原 → 因人而異 + 食安中心
    "豆干": ("caution", ALLERGEN.format(what="大豆製品，", who="大豆過敏"),
             False, ["大豆"], [CFS]),
    "鮮奶油": ("caution", ALLERGEN.format(what="奶製品，", who="奶類過敏"),
               False, ["奶"], [CFS]),
    "吉士粉": ("caution", ALLERGEN.format(what="通常含奶成分，", who="奶類過敏"),
               False, ["奶"], [CFS]),
    "美乃滋": ("caution", ALLERGEN.format(what="含蛋，", who="蛋過敏"),
               False, ["蛋"], [CFS]),
    "酥炸粉": ("caution", ALLERGEN.format(what="通常含小麥粉，", who="小麥過敏"),
               False, ["小麥"], [CFS]),
    "春捲皮": ("caution", ALLERGEN.format(what="小麥製品，", who="小麥過敏"),
               False, ["小麥"], [CFS]),
    "小魚乾": ("caution", ALLERGEN.format(what="魚類製品，", who="魚類過敏"),
               False, ["魚"], [CFS]),
    # 醃製／發酵／乾製 → 組織胺留意（證據有限，需資深審核）
    "酸菜": ("caution", HIST.format(note="醃製發酵蔬菜"), True, ["組織胺"], [PMC]),
    "鹹菜": ("caution", HIST.format(note="醃製發酵蔬菜"), True, ["組織胺"], [PMC]),
    "梅乾菜": ("caution", HIST.format(note="醃製發酵蔬菜"), True, ["組織胺"], [PMC]),
    "福菜": ("caution", HIST.format(note="醃製發酵蔬菜"), True, ["組織胺"], [PMC]),
    "筍乾": ("caution", HIST.format(note="乾製醃漬蔬菜"), True, ["組織胺"], [PMC]),
    "長豆乾": ("caution", HIST.format(note="乾製蔬菜"), True, ["組織胺"], [PMC]),
    "鹹豬肉": ("caution", HIST.format(note="醃製肉類"), True, ["組織胺"], [PMC]),
    "雞高湯": ("caution", HIST.format(note="長時間熬煮湯底"), True, ["組織胺"], [PMC]),
    "樹子醬": ("caution", HIST.format(note="醃漬發酵調味品"), True, ["組織胺"], [PMC]),
    # 柑橘類 → 組織胺留意
    "金桔": ("caution", HIST.format(note="柑橘類，部分低組織胺飲食列為須留意，因人而異；"),
             True, ["組織胺"], [PMC]),
    "桔醬": ("caution", HIST.format(note="金桔（柑橘類）製品，部分低組織胺飲食列為須留意，因人而異；"),
             True, ["組織胺"], [PMC]),
    # 水楊酸
    "柿餅": ("caution", ("乾果或含亞硫酸鹽及水楊酸，敏感者留意（依據：水楊酸／亞硫酸鹽；"
             "適用：對水楊酸或亞硫酸鹽敏感者（證據有限）；來源：Swain 1985 食物水楊酸分析（PubMed））"),
             True, ["水楊酸"], [SWAIN]),
    "辣椒": ("caution", ("辛香料水楊酸含量較高，只作留意（依據：水楊酸；"
             "適用：對水楊酸敏感者（證據有限）；來源：Swain 1985 食物水楊酸分析（PubMed））"),
             True, ["水楊酸"], [SWAIN]),
    "辣味露": ("caution", ("辣椒類調味品，辛香料水楊酸含量較高，只作留意（依據：水楊酸；"
               "適用：對水楊酸敏感者（證據有限）；來源：Swain 1985 食物水楊酸分析（PubMed））"),
               True, ["水楊酸"], [SWAIN]),
    # 花粉交叉／LTP
    "艾草": ("caution", ("艾屬植物與花粉-食物交叉反應有文獻記錄（mugwort–celery–spice "
             "syndrome），已確診相關花粉過敏者留意（依據：花粉交叉；證據有限；"
             "來源：花粉-食物過敏症候群綜述）"), True, ["花粉交叉"], [POLLEN]),
    "枸杞": ("caution", ("茄科植物；有枸杞過敏及與桃、番茄等 LTP 交叉反應個案報告，"
             "食物過敏人士留意（依據：交叉反應；來源：PubMed 23101309）"),
             True, ["花粉交叉"], [GOJI]),
    # 資料不足
    "木鱉子": ("unrated", "資料不足：罕見食材，未找到可靠來源評估", True, [], []),
    "仙草": ("unrated", "資料不足：未找到可靠來源評估", True, [], []),
    "鮮味露": ("unrated", "資料不足：成分因品牌而異，未找到可靠來源評估", True, [], []),
}


def main():
    stats = {"ok": 0, "skip": 0, "missing": []}
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        for name, (rating, reason, senior, allergens, evs) in PLAN.items():
            row = conn.execute(
                "SELECT id, reviewed FROM ingredient WHERE name_zh = %s", (name,)
            ).fetchone()
            if row is None:
                stats["missing"].append(name)
                continue
            if row["reviewed"]:
                stats["skip"] += 1
                print(f"SKIP reviewed: {name}")
                continue
            iid = row["id"]
            conn.execute(
                "UPDATE ingredient SET eczema_rating = %s, rating_reason = %s,"
                " needs_senior_review = %s WHERE id = %s",
                (rating, reason, senior, iid),
            )
            repo.audit(conn, "ingredient", iid, "edit",
                       {"rating": [None, rating], "rating_reason": [None, reason],
                        "needs_senior_review": [None, senior],
                        "note": "bulk rating proposal"})
            for atype in allergens:
                aid = conn.execute(
                    "SELECT id FROM allergen WHERE name_zh = %s", (atype,)).fetchone()
                if aid:
                    errs, _ = repo.add_allergen(conn, iid, aid["id"], None)
                    if errs:
                        print(f"ALLERGEN FAIL {name}/{atype}: {errs}")
            for title, url in evs:
                errs, _ = repo.add_evidence(conn, iid, title, url, "other", "")
                if errs:
                    print(f"EVIDENCE FAIL {name}: {errs}")
            stats["ok"] += 1
        conn.commit()
    print(stats)


if __name__ == "__main__":
    main()
