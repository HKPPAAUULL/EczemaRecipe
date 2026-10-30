"""Pure review rules for the admin backend (no DB, no I/O).

Safety-critical: these decide what may be marked reviewed / published.
Every function returns a list of Chinese error messages (empty = OK).
"""

from urllib.parse import urlsplit

RATINGS = ("suitable", "caution", "trigger", "unrated")
SEVERITIES = ("low", "medium", "high")
RECIPE_ACTIONS = ("publish", "reject", "resubmit")

FORBIDDEN_TERMS = ("治療", "根治", "會導致", "抗濕疹", "抗炎", "消炎", "療效", "保證")
RECIPE_FORBIDDEN_TERMS = FORBIDDEN_TERMS + (
    "舒緩", "修復", "緩解", "改善濕疹", "對濕疹有益", "低敏", "抗敏",
    "不致敏", "無致敏", "過敏者適用", "安全食用", "無過敏原",
)

_TRANSITIONS = {
    "publish": {"pending_review", "draft"},
    "reject": {"pending_review", "draft", "published"},
    "resubmit": {"draft", "rejected", "published"},
}
ACTION_TARGET = {
    "publish": "published",
    "reject": "rejected",
    "resubmit": "pending_review",
}
ACTION_LABELS = {"publish": "發佈", "reject": "退回", "resubmit": "重新送審"}


def find_forbidden_terms(text: str | None) -> list[str]:
    text = text or ""
    return [t for t in FORBIDDEN_TERMS if t in text]


def find_recipe_forbidden_terms(text: str | None) -> list[str]:
    text = text or ""
    return [t for t in RECIPE_FORBIDDEN_TERMS if t in text]


def is_http_url(url: str | None) -> bool:
    if not url or url != url.strip() or any(c.isspace() for c in url):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def validate_ingredient_fields(rating: str, reason: str | None) -> list[str]:
    errors = []
    if rating not in RATINGS:
        errors.append("評級無效。")
        return errors
    reason = (reason or "").strip()
    if rating in ("caution", "trigger") and not reason:
        errors.append("評級為「因人而異」或「常見誘發」時必須填寫評級原因。")
    bad = find_forbidden_terms(reason)
    if bad:
        errors.append(
            "評級原因不得使用療效或絕對用語：" + "、".join(bad) + "。請改用「常見」「可能」「因人而異」。"
        )
    return errors


def validate_ingredient_review(
    rating: str,
    reason: str | None,
    has_major_allergen: bool,
    evidence_urls: list[str | None],
) -> list[str]:
    errors = validate_ingredient_fields(rating, reason)
    if rating == "suitable" and has_major_allergen:
        errors.append("此食材連結了九大過敏原，不可審核為「一般適合」（至少須為「因人而異」）。")
    if rating == "trigger" and not any(is_http_url(u) for u in evidence_urls):
        errors.append("評級為「常見誘發」必須至少有一筆含 http(s) 網址的證據才可審核。")
    return errors


def validate_evidence(
    title: str | None, url: str | None, source_type: str | None, year_raw: str | None
) -> tuple[dict | None, list[str]]:
    errors = []
    title = (title or "").strip()
    url = (url or "").strip()
    source_type = (source_type or "").strip() or "other"
    year_raw = (year_raw or "").strip()
    if not title:
        errors.append("證據標題不可為空。")
    if not is_http_url(url):
        errors.append("證據網址必須是有效的 http(s) 網址。")
    year = None
    if year_raw:
        if not year_raw.isdigit() or not 1800 <= int(year_raw) <= 2100:
            errors.append("年份須為 1800–2100 的整數。")
        else:
            year = int(year_raw)
    if errors:
        return None, errors
    return {"title": title, "url": url, "source_type": source_type, "year": year}, []


def parse_aliases(text: str | None) -> list[str]:
    seen: dict[str, None] = {}
    for part in (text or "").replace("，", ",").replace("、", ",").replace("\n", ",").split(","):
        part = part.strip()
        if part:
            seen.setdefault(part)
    return list(seen)


def parse_score(raw: str | None) -> tuple[float | None, list[str]]:
    raw = (raw or "").strip()
    if not raw:
        return None, []
    try:
        value = float(raw)
    except ValueError:
        return None, ["友善分數須為 0–100 的數字。"]
    if not 0 <= value <= 100:
        return None, ["友善分數須為 0–100 的數字。"]
    return value, []


def parse_positive_int(raw: str | None, label: str, minimum: int) -> tuple[int | None, list[str]]:
    raw = (raw or "").strip()
    if not raw:
        return None, []
    if not raw.isdigit() or int(raw) < minimum or int(raw) > 100000:
        return None, [f"{label}須為整數（最小 {minimum}）。"]
    return int(raw), []


def validate_publish(unmatched: list[str], matched: list[dict]) -> list[str]:
    errors = []
    if unmatched:
        errors.append("仍有未配對食材：" + "、".join(unmatched) + "。")
    unreviewed = [m["name_zh"] for m in matched if not m["reviewed"]]
    if unreviewed:
        errors.append("以下已配對食材尚未審核：" + "、".join(unreviewed) + "。")
    if not any(not m["is_staple"] for m in matched):
        errors.append("至少需要 1 個已配對的非調味料食材。")
    return errors


def check_transition(current: str, action: str) -> str | None:
    if action not in _TRANSITIONS:
        return "無效的操作。"
    if current not in _TRANSITIONS[action]:
        return f"目前狀態（{current}）不可執行「{ACTION_LABELS[action]}」。"
    return None


def merge_raw_text(existing: str, new: str) -> str:
    parts = [p for p in existing.split("；") if p]
    if new and new not in parts:
        parts.append(new)
    return "；".join(parts)


def remove_item(items: list[str], item: str) -> list[str]:
    return [i for i in items if i != item]
