"""TFDA 食品營養成分資料集：篩選、配對、產生參考 CSV、匯入 DB。

資料來源：衛生福利部食品藥物管理署「食品營養成分資料集」
（https://data.gov.tw/dataset/8543，政府資料開放授權條款-第1版，須顯名）。

管線分兩步：
1. ``--download`` + ``--build``：下載原始 ZIP/CSV 到 ``data/raw/``（不入版控），
   篩選後產生小而可人工審核的 ``data/reference/nutrition_tfda.csv``（入版控）
   與配對報告 ``data/reference/nutrition_match_report.md``。
2. 匯入：只讀參考 CSV（不依賴網路），upsert data_source / nutrient /
   ingredient_nutrient，單一交易、冪等。

配對規則（確定性、保守、寧缺勿錯）：
- 名稱正規化：NFKC 全半形統一 + 移除所有空白；另對 TFDA「樣品名稱」與
  「俗名」各產生去括號變體（``雞蛋(白殼)`` → ``雞蛋``）與去「平均值」
  後綴變體（``雞蛋平均值`` → ``雞蛋``），全部做精確比對。
- 候選分層（種子食材端名稱優先於別名；TFDA 端樣品名稱優先於俗名）：
  第 1 層＝name_zh ↔ 樣品名稱；第 2 層＝name_zh ↔ 俗名 或 別名 ↔ 樣品名稱；
  第 3 層＝別名 ↔ 俗名。取第一個有「合格候選」的層。
- 「合格候選」（原料／生鮮判定）：食品分類不得為加工調理食品及其他類、
  糕餅點心類、飲料類、糖類；樣品狀態以「生」開頭者合格；其餘樣品狀態、
  樣品名稱或（無狀態時）內容物描述含加工標記（熟、乾、醃、罐、烘、烤、
  炸、燻、包裝、瓶裝、盒裝、製品、發酵、現調、鹽酥等）者排除；
  樣品名稱以「粉」結尾（磨粉製品）排除。
- 採用規則：合格候選恰好 1 個 → 採用；多個時若恰好 1 個為 TFDA 官方
  「平均值」樣品 → 採用該平均值（報告中標示供人工複查）；其餘一律跳過。
- 數值：只取「每100克含量」可解析為數字且 ≥0 者；空值與「1.00/1.85」等
  比例字串略過；單位須與白名單預期一致（ug 正規化為 µg）。
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAW_CSV = REPO_ROOT / "data" / "raw" / "20_2.csv"
DEFAULT_NUTRITION_CSV = REPO_ROOT / "data" / "reference" / "nutrition_tfda.csv"
DEFAULT_MATCH_REPORT = REPO_ROOT / "data" / "reference" / "nutrition_match_report.md"
TFDA_DOWNLOAD_URL = "https://data.fda.gov.tw/data/opendata/export/20/csv"
TFDA_SOURCE_NAME = "TFDA 食品營養成分資料集"
TFDA_SOURCE_URL = "https://data.gov.tw/dataset/8543"
TFDA_SOURCE_LICENSE = "政府資料開放授權條款-第1版"

# 分析項 -> (nutrient.name, nutrient.unit)。先核對實際「分析項」名稱後定稿。
NUTRIENT_WHITELIST = {
    "熱量": ("熱量", "kcal"),
    "粗蛋白": ("粗蛋白", "g"),
    "粗脂肪": ("粗脂肪", "g"),
    "總碳水化合物": ("總碳水化合物", "g"),
    "膳食纖維": ("膳食纖維", "g"),
    "鈉": ("鈉", "mg"),
    "鈣": ("鈣", "mg"),
    "鐵": ("鐵", "mg"),
    "鋅": ("鋅", "mg"),
    "維生素D總量(ug)": ("維生素D", "µg"),
    "維生素E總量": ("維生素E", "mg"),
    "廿碳五烯酸(20:5)": ("EPA", "mg"),
    "廿二碳六烯酸(22:6)": ("DHA", "mg"),
    "次亞麻油酸(18:3)": ("α-次亞麻油酸", "mg"),
}
NUTRIENT_ORDER = [v[0] for v in NUTRIENT_WHITELIST.values()]

# 食品加工判定（見模組 docstring）
PROCESSED_CATEGORIES = {"加工調理食品及其他類", "糕餅點心類", "飲料類", "糖類"}
PROCESSED_MARKERS = (
    "熟", "乾", "醃", "罐", "燻", "煙", "炸", "烘", "烤", "包裝",
    "瓶", "盒裝", "製品", "加工", "發酵", "釀", "現調", "現榨",
    "濃縮", "鹽酥", "糖漬", "蜜餞",
)
DESC_PROCESSED_MARKERS = (
    "熟", "醃", "乾", "罐", "烘", "烤", "炸", "燻", "煙", "煮",
    "發酵", "包裝", "瓶", "盒裝", "滷", "燉", "蒸",
)

REFERENCE_COLUMNS = [
    "ingredient_name_zh",
    "tfda_integration_id",
    "tfda_sample_name",
    "nutrient_name",
    "unit",
    "amount_per_100g",
]
ALLOWED_UNITS = {"g", "mg", "µg", "kcal"}

_UNIT_ALIASES = {"ug": "µg", "i.u.": "IU"}


class NutritionValidationError(ValueError):
    """Raised for invalid raw/reference data; message carries context."""


def normalize_text(s: str | None) -> str:
    """NFKC 全半形統一後移除所有空白。"""
    return "".join(unicodedata.normalize("NFKC", s or "").split())


def match_keys(name: str | None) -> set[str]:
    """正規化比對鍵：原名、去括號、去「平均值」後綴的變體。"""
    keys = {normalize_text(name)}
    base = re.sub(r"[（(][^）)]*[）)]", "", name or "")
    keys.add(normalize_text(base))
    keys |= {
        k[: -len("平均值")] for k in tuple(keys) if k.endswith("平均值")
    }
    return {k for k in keys if k}


def normalize_unit(unit: str | None) -> str:
    return _UNIT_ALIASES.get((unit or "").strip().lower(), (unit or "").strip())


def parse_amount(cell: str | None) -> float | None:
    """「每100克含量」→ float；空值、非數字（如 ``1.00/1.85`` 比例）、負數 → None。"""
    v = (cell or "").strip()
    if not v:
        return None
    try:
        amount = float(v)
    except ValueError:
        return None
    return amount if amount >= 0 else None


@dataclass
class TfdaSample:
    integration_id: str
    sample_name: str
    food_category: str
    sample_state: str
    description: str
    name_keys: set[str]
    common_keys: set[str]
    # 分析項 -> (資料類別優先序, nutrient_name, unit, amount)；已過白名單
    nutrients: dict[str, tuple[int, str, str, float]] = field(default_factory=dict)

    @property
    def is_average(self) -> bool:
        return self.sample_name.endswith("平均值")


def _sample_state(description: str) -> str:
    m = re.search(r"樣品狀態:([^;]+)", description or "")
    return m.group(1).strip() if m else ""


def _store_nutrient(sample: TfdaSample, dtype: str, item: str,
                    unit: str, amount: float | None) -> None:
    """白名單分析項入庫：單位須一致；同項優先保留『樣品平均值』列。"""
    spec = NUTRIENT_WHITELIST.get(item)
    if spec is None or amount is None:
        return
    nutrient_name, expected_unit = spec
    if normalize_unit(unit) != expected_unit:
        return
    priority = 0 if dtype == "樣品平均值" else 1
    prev = sample.nutrients.get(nutrient_name)
    if prev is None or priority < prev[0]:
        sample.nutrients[nutrient_name] = (
            priority, nutrient_name, expected_unit, amount
        )


def load_tfda_samples(path: str | Path) -> dict[str, TfdaSample]:
    """解析 TFDA 原始 CSV（UTF-8 BOM），每個整合編號一個 TfdaSample。"""
    samples: dict[str, TfdaSample] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"食品分類", "資料類別", "整合編號", "樣品名稱", "俗名",
                    "內容物描述", "分析項", "含量單位", "每100克含量"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise NutritionValidationError(
                f"raw CSV missing columns: {sorted(missing)}"
            )
        for row in reader:
            iid = (row["整合編號"] or "").strip()
            if not iid:
                continue
            sample = samples.get(iid)
            if sample is None:
                name_keys = match_keys(row["樣品名稱"])
                common_keys: set[str] = set()
                for alias in (row["俗名"] or "").split(","):
                    if alias.strip():
                        common_keys |= match_keys(alias)
                sample = TfdaSample(
                    integration_id=iid,
                    sample_name=(row["樣品名稱"] or "").strip(),
                    food_category=(row["食品分類"] or "").strip(),
                    sample_state=_sample_state(row["內容物描述"] or ""),
                    description=row["內容物描述"] or "",
                    name_keys=name_keys,
                    common_keys=common_keys,
                )
                samples[iid] = sample
            _store_nutrient(
                sample,
                (row["資料類別"] or "").strip(),
                (row["分析項"] or "").strip(),
                row["含量單位"],
                parse_amount(row["每100克含量"]),
            )
    return samples


def is_unprocessed(sample: TfdaSample) -> bool:
    """原料／生鮮判定（見模組 docstring）：加工品不採用。"""
    if sample.food_category in PROCESSED_CATEGORIES:
        return False
    if sample.sample_state.startswith("生"):
        return True
    if any(m in sample.sample_state for m in PROCESSED_MARKERS):
        return False
    if any(m in sample.sample_name for m in PROCESSED_MARKERS):
        return False
    if not sample.sample_state and any(
        m in sample.description for m in DESC_PROCESSED_MARKERS
    ):
        return False
    return not sample.sample_name.endswith("粉")


@dataclass
class MatchResult:
    ingredient_name_zh: str
    status: str  # matched | matched_avg | no_candidate | no_eligible | ambiguous
    via: str  # name | alias | ''（未配對）
    sample: TfdaSample | None = None
    candidates: list[TfdaSample] = field(default_factory=list)


def match_ingredient(
    name_zh: str,
    aliases: list[str],
    name_index: dict[str, set[str]],
    common_index: dict[str, set[str]],
    samples: dict[str, TfdaSample],
) -> MatchResult:
    """分層精確配對一個種子食材（規則見模組 docstring）。"""
    keys_name = match_keys(name_zh)
    keys_alias: set[str] = set()
    for a in aliases:
        keys_alias |= match_keys(a)

    def gather(keys: set[str], index: dict[str, set[str]]) -> set[str]:
        out: set[str] = set()
        for k in keys:
            out |= index.get(k, set())
        return out

    if not gather(keys_name | keys_alias, name_index) and not gather(
        keys_name | keys_alias, common_index
    ):
        return MatchResult(name_zh, "no_candidate", "")

    tiers = [
        ("name", gather(keys_name, name_index)),
        ("alias",
         gather(keys_name, common_index) | gather(keys_alias, name_index)),
        ("alias", gather(keys_alias, common_index)),
    ]
    for via, pool in tiers:
        eligible = sorted(
            (samples[i] for i in pool if is_unprocessed(samples[i])),
            key=lambda s: s.integration_id,
        )
        if not eligible:
            continue
        if len(eligible) == 1:
            return MatchResult(name_zh, "matched", via, eligible[0], eligible)
        averages = [s for s in eligible if s.is_average]
        if len(averages) == 1:
            return MatchResult(
                name_zh, "matched_avg", via, averages[0], eligible
            )
        return MatchResult(name_zh, "ambiguous", via, None, eligible)
    seen: dict[str, TfdaSample] = {}
    for _, pool in tiers:
        for i in pool:
            seen[i] = samples[i]
    all_candidates = sorted(seen.values(), key=lambda s: s.integration_id)
    return MatchResult(name_zh, "no_eligible", "", None, all_candidates)


def build_name_indexes(
    samples: dict[str, TfdaSample],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    name_index: dict[str, set[str]] = {}
    common_index: dict[str, set[str]] = {}
    for iid, s in samples.items():
        for k in s.name_keys:
            name_index.setdefault(k, set()).add(iid)
        for k in s.common_keys:
            common_index.setdefault(k, set()).add(iid)
    return name_index, common_index


@dataclass
class ReferenceRow:
    ingredient_name_zh: str
    tfda_integration_id: str
    tfda_sample_name: str
    nutrient_name: str
    unit: str
    amount_per_100g: float


def build_reference_rows(matches: list[MatchResult]) -> list[ReferenceRow]:
    """配對成功的食材 → 參考 CSV 列（每 100g 白名單營養素）。"""
    rows: list[ReferenceRow] = []
    for m in matches:
        if m.sample is None:
            continue
        for name in NUTRIENT_ORDER:
            entry = m.sample.nutrients.get(name)
            if entry is None:
                continue
            _, nutrient_name, unit, amount = entry
            rows.append(
                ReferenceRow(
                    m.ingredient_name_zh, m.sample.integration_id,
                    m.sample.sample_name, nutrient_name, unit, amount,
                )
            )
    rows.sort(key=lambda r: (r.ingredient_name_zh, NUTRIENT_ORDER.index(r.nutrient_name)))
    return rows


def write_reference_csv(rows: list[ReferenceRow], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(REFERENCE_COLUMNS)
        for r in rows:
            writer.writerow([
                r.ingredient_name_zh, r.tfda_integration_id,
                r.tfda_sample_name, r.nutrient_name, r.unit,
                r.amount_per_100g,
            ])


def write_match_report(matches: list[MatchResult], path: str | Path) -> None:
    counts: dict[str, int] = {}
    for m in matches:
        counts[m.status] = counts.get(m.status, 0) + 1
    lines = [
        "# TFDA 營養資料配對報告",
        "",
        "由 `python -m app.cli import-nutrition --build` 產生；供人工複查。",
        (
            f"資料來源：{TFDA_SOURCE_NAME}（{TFDA_SOURCE_URL}，"
            f"{TFDA_SOURCE_LICENSE}）。"
        ),
        "",
        "## 統計",
        "",
        f"- 配對成功（唯一候選）：{counts.get('matched', 0)}",
        f"- 配對成功（多候選取官方平均值）：{counts.get('matched_avg', 0)}",
        f"- 無候選：{counts.get('no_candidate', 0)}",
        f"- 有候選但全部為加工品／不合格：{counts.get('no_eligible', 0)}",
        f"- 多候選未能決定（跳過）：{counts.get('ambiguous', 0)}",
        "",
        "## 配對結果",
        "",
        "| 食材 | 狀態 | 比對層 | TFDA 樣品 |",
        "|---|---|---|---|",
    ]
    status_labels = {
        "matched": "配對",
        "matched_avg": "配對（平均值）",
        "no_candidate": "無候選",
        "no_eligible": "全為加工品",
        "ambiguous": "多候選跳過",
    }
    for m in matches:
        sample = (
            f"{m.sample.integration_id} {m.sample.sample_name}"
            if m.sample else "—"
        )
        lines.append(
            f"| {m.ingredient_name_zh} | {status_labels[m.status]} "
            f"| {m.via or '—'} | {sample} |"
        )
    lines += ["", "## 跳過／待人工複查清單", ""]
    for m in matches:
        if m.status in {"matched", "matched_avg"}:
            continue
        lines.append(f"### {m.ingredient_name_zh}（{status_labels[m.status]}）")
        if m.candidates:
            for c in m.candidates:
                state = c.sample_state or "（無樣品狀態）"
                lines.append(
                    f"- `{c.integration_id}` {c.sample_name}"
                    f"（{c.food_category}；{state}）"
                )
        lines.append("")
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def build_reference(
    raw_csv: str | Path,
    seed_csv: str | Path,
    synonyms_csv: str | Path,
    out_csv: str | Path,
    report_path: str | Path,
) -> list[MatchResult]:
    """raw TFDA CSV + 種子食材 → 參考 CSV + 配對報告。"""
    from app.importer import (
        load_synonym_groups,
        merge_synonym_aliases,
        parse_seed_csv,
    )

    seed_rows = parse_seed_csv(seed_csv)
    synonyms = Path(synonyms_csv)
    if synonyms.is_file():
        merge_synonym_aliases(seed_rows, load_synonym_groups(synonyms))
    samples = load_tfda_samples(raw_csv)
    name_index, common_index = build_name_indexes(samples)
    matches = [
        match_ingredient(r.name_zh, r.aliases, name_index, common_index, samples)
        for r in seed_rows
    ]
    write_reference_csv(build_reference_rows(matches), out_csv)
    write_match_report(matches, report_path)
    return matches


def parse_reference_csv(path: str | Path) -> list[ReferenceRow]:
    """解析並驗證參考 CSV；欄位／單位／數值不符即報錯（含行號）。"""
    rows: list[ReferenceRow] = []
    seen: set[tuple[str, str]] = set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = set(REFERENCE_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise NutritionValidationError(
                f"reference CSV missing columns: {sorted(missing)}"
            )
        for i, raw in enumerate(reader, start=2):
            name = (raw["ingredient_name_zh"] or "").strip()
            iid = (raw["tfda_integration_id"] or "").strip()
            nutrient = (raw["nutrient_name"] or "").strip()
            unit = (raw["unit"] or "").strip()
            if not name or not iid or not nutrient:
                raise NutritionValidationError(
                    f"row {i}: ingredient/integration_id/nutrient is empty"
                )
            if unit not in ALLOWED_UNITS:
                raise NutritionValidationError(
                    f"row {i} ({name}): invalid unit {unit!r}"
                )
            amount = parse_amount(raw["amount_per_100g"])
            if amount is None:
                raise NutritionValidationError(
                    f"row {i} ({name}): invalid amount "
                    f"{raw['amount_per_100g']!r}"
                )
            if (name, nutrient) in seen:
                raise NutritionValidationError(
                    f"row {i}: duplicate ({name}, {nutrient})"
                )
            seen.add((name, nutrient))
            rows.append(
                ReferenceRow(
                    name, iid,
                    (raw["tfda_sample_name"] or "").strip(),
                    nutrient, unit, amount,
                )
            )
    if not rows:
        raise NutritionValidationError("reference CSV has no data rows")
    return rows


@dataclass
class NutritionImportSummary:
    rows_total: int = 0
    ingredients_matched: int = 0
    ingredients_missing: int = 0
    missing_names: list[str] = field(default_factory=list)
    nutrients_created: int = 0
    values_written: int = 0
    data_source_created: bool = False

    def format(self, dry_run: bool = False) -> str:
        lines = [
            (
                "import-nutrition summary"
                f"{' (dry-run: rolled back)' if dry_run else ''}:"
            ),
            f"  reference rows: {self.rows_total}",
            f"  ingredients matched in DB: {self.ingredients_matched}",
            (
                "  ingredients missing in DB (skipped): "
                f"{self.ingredients_missing}"
            ),
            f"  nutrients created: {self.nutrients_created}",
            f"  ingredient_nutrient rows written: {self.values_written}",
            f"  TFDA data_source created: {self.data_source_created}",
        ]
        if self.missing_names:
            lines.append(
                "  missing ingredients: " + ", ".join(self.missing_names)
            )
        return "\n".join(lines)


def _ensure_tfda_source(conn) -> tuple[int, bool]:
    row = conn.execute(
        "SELECT id FROM data_source WHERE name = %s", (TFDA_SOURCE_NAME,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE data_source SET url = %s, license = %s, kind = 'nutrition' "
            "WHERE id = %s",
            (TFDA_SOURCE_URL, TFDA_SOURCE_LICENSE, row[0]),
        )
        return row[0], False
    row = conn.execute(
        """INSERT INTO data_source (name, url, license, kind)
           VALUES (%s, %s, %s, 'nutrition') RETURNING id""",
        (TFDA_SOURCE_NAME, TFDA_SOURCE_URL, TFDA_SOURCE_LICENSE),
    ).fetchone()
    return row[0], True


def import_nutrition(conn, rows: list[ReferenceRow]) -> NutritionImportSummary:
    """匯入參考列：只寫入已存在的 ingredient，不新增、不改 reviewed/rating。

    必須由呼叫方持有交易（``run_import`` 提供）。
    """
    source_id, created = _ensure_tfda_source(conn)
    summary = NutritionImportSummary(
        rows_total=len(rows), data_source_created=created
    )

    nutrient_ids: dict[tuple[str, str], int] = {}
    for name in NUTRIENT_ORDER:
        unit = next(u for n, u in NUTRIENT_WHITELIST.values() if n == name)
        cur = conn.execute(
            "INSERT INTO nutrient (name, unit) VALUES (%s, %s) "
            "ON CONFLICT (name, unit) DO NOTHING",
            (name, unit),
        )
        if cur.rowcount:
            summary.nutrients_created += 1
        nutrient_ids[(name, unit)] = conn.execute(
            "SELECT id FROM nutrient WHERE name = %s AND unit = %s",
            (name, unit),
        ).fetchone()[0]

    ingredient_ids = {
        name: iid
        for iid, name in conn.execute("SELECT id, name_zh FROM ingredient")
    }
    for r in rows:
        iid = ingredient_ids.get(r.ingredient_name_zh)
        if iid is None:
            if r.ingredient_name_zh not in summary.missing_names:
                summary.missing_names.append(r.ingredient_name_zh)
            continue
        conn.execute(
            """INSERT INTO ingredient_nutrient
                   (ingredient_id, nutrient_id, amount_per_100g, source_id)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (ingredient_id, nutrient_id, source_id)
               DO UPDATE SET amount_per_100g = EXCLUDED.amount_per_100g""",
            (iid, nutrient_ids[(r.nutrient_name, r.unit)],
             r.amount_per_100g, source_id),
        )
        summary.values_written += 1
    summary.ingredients_missing = len(summary.missing_names)
    summary.ingredients_matched = len(
        {r.ingredient_name_zh for r in rows} - set(summary.missing_names)
    )
    return summary


def run_import(
    database_url: str, rows: list[ReferenceRow], dry_run: bool = False
) -> NutritionImportSummary:
    """單一交易執行匯入；dry-run 結尾 rollback。"""
    import psycopg  # lazy: unit tests run without the driver installed

    with psycopg.connect(database_url) as conn:
        try:
            summary = import_nutrition(conn, rows)
            if dry_run:
                conn.rollback()
            else:
                conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return summary


def download_raw(url: str, dest_dir: str | Path) -> Path:
    """下載 TFDA 原始資料（ZIP 或 CSV）到 dest_dir，回傳解壓後 CSV 路徑。"""
    import urllib.request

    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "EczemaRecipe/0.3"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        blob = resp.read()
    if zipfile.is_zipfile(io.BytesIO(blob)):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            names = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not names:
                raise NutritionValidationError("downloaded ZIP contains no CSV")
            z.extract(names[0], dest)
            return dest / names[0]
    out = dest / "tfda_nutrition.csv"
    out.write_bytes(blob)
    return out
