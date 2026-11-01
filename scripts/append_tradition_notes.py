import csv
import io

CC = "消費者委員會《選擇》第547期〈濕疹 中醫內外入手有療法〉(2022)"
CU = "https://www.consumer.org.hk/tc/article/547-eczema/547-eczema-daily-care"
CM = "衞生署中醫藥規管辦公室〈服藥忌口〉"
MU = ("https://www.cmro.gov.hk/html/b5/useful_information/public_health/"
      "feature_articles/Knowledge_of_Taking_Chinese_Medicines_Precautions_and_Storage_Method.html")

rows = []


def fawu(n, what):
    rows.append([n, "fawu", f"中醫傳統說法將{what}列為「發物」，認為濕疹患者宜戒食或留意。", CC, CU])


def fawu_cmro(n):
    rows.append([n, "fawu",
                 "衞生署中醫藥規管辦公室指出，皮膚病患者在服藥期間應忌食魚、蝦、蟹等被稱為「腥膻發物」的食物。",
                 CM, MU])


def hot(n, what):
    rows.append([n, "warm_hot", f"中醫認為{what}屬濕熱／燥熱之物，偏熱體質人士宜少食。", CC, CU])


def neu(n, what):
    rows.append([n, "neutral", f"消委會文章將{what}列為中醫認為可補脾益氣、祛濕的平性食物之一。", CC, CU])


def cool(n, what):
    rows.append([n, "cool", f"消委會文章將{what}列為中醫認為可幫助清熱的涼性食材之一，適合體質偏熱者。", CC, CU])


# 發物（消委會明列竹筍）
fawu("竹筍", "竹筍")
fawu("筍乾", "竹筍（筍乾為其乾製品）")
# 腥膻發物（衞生署：皮膚病患者服藥期間應忌食魚、蝦、蟹）
for n in ["鯇魚", "鱸魚", "鯽魚", "石斑", "鱈魚", "吞拿魚", "鯖魚", "龍脷柳",
          "黃花魚", "魷魚", "墨魚", "龍蝦", "蝦米", "小魚乾"]:
    fawu_cmro(n)
fawu("三文魚", "魚類海產")
fawu_cmro("三文魚")
# 燥熱（消委會列辣椒）
hot("辣椒", "辣椒")
hot("辣味露", "辣椒類調味品")
# 平性食療（消委會）
for n, what in [("淮山", "淮山"), ("枸杞", "杞子"), ("紅豆", "紅豆／赤小豆"),
                ("節瓜", "節瓜"), ("豬瘦肉", "豬肉"), ("三文魚", "三文魚")]:
    neu(n, what)
# 涼性食療（消委會）
for n, what in [("綠豆", "綠豆"), ("西洋菜", "西洋菜"), ("芥蘭", "芥蘭"), ("青瓜", "青瓜"),
                ("荸薺", "馬蹄"), ("火龍果", "火龍果"), ("西瓜", "西瓜"), ("梨", "雪梨"),
                ("鴨肉", "鴨肉")]:
    cool(n, what)

with io.open("data/seed/tradition_notes.csv", encoding="utf-8-sig") as f:
    existing = {(r["ingredient_zh"], r["note"]) for r in csv.DictReader(f)}
with io.open("data/seed/tradition_notes.csv", "a", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    n = 0
    for r in rows:
        if (r[0], r[2]) not in existing:
            w.writerow(r)
            n += 1
print("appended", n)
