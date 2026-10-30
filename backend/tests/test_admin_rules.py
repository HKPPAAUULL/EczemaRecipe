"""Pure unit tests for the admin review rules (no DB)."""

import pytest

from app.admin import rules


def ev(url="https://example.org/a"):
    return [url]


@pytest.mark.parametrize("term", rules.FORBIDDEN_TERMS)
def test_each_forbidden_term_is_detected(term):
    assert rules.find_forbidden_terms(f"食用後{term}。") == [term]


def test_forbidden_terms_exact_list():
    assert rules.FORBIDDEN_TERMS == (
        "治療", "根治", "會導致", "抗濕疹", "抗炎", "消炎", "療效", "保證")


def test_clean_reason_has_no_forbidden_terms():
    assert rules.find_forbidden_terms("為常見食物過敏原之一；已確診過敏者須避免") == []
    assert rules.find_forbidden_terms(None) == []


@pytest.mark.parametrize("url", [
    "http://a.org", "https://a.org/x?y=1", "https://a.org:8080/p"])
def test_http_urls_accepted(url):
    assert rules.is_http_url(url)


@pytest.mark.parametrize("url", [
    None, "", "ftp://a.org", "javascript:alert(1)", "https://", "a.org",
    "https://a.org/ x", " https://a.org", "//a.org", "data:text/html,x"])
def test_non_http_urls_rejected(url):
    assert not rules.is_http_url(url)


@pytest.mark.parametrize("rating", ["caution", "trigger"])
@pytest.mark.parametrize("reason", [None, "", "   "])
def test_caution_trigger_need_reason(rating, reason):
    errors = rules.validate_ingredient_fields(rating, reason)
    assert any("必須填寫評級原因" in e for e in errors)


@pytest.mark.parametrize("rating", ["suitable", "unrated"])
def test_suitable_unrated_allow_empty_reason(rating):
    assert rules.validate_ingredient_fields(rating, None) == []


def test_invalid_rating_rejected():
    assert rules.validate_ingredient_fields("great", "x") == ["評級無效。"]


def test_reason_with_forbidden_term_rejected_for_every_rating():
    for rating in rules.RATINGS:
        errors = rules.validate_ingredient_fields(rating, "可以根治濕疹")
        assert any("根治" in e for e in errors)


def test_trigger_without_evidence_cannot_be_reviewed():
    errors = rules.validate_ingredient_review("trigger", "有權威指引", False, [])
    assert any("證據" in e for e in errors)


def test_trigger_with_null_or_bad_url_evidence_cannot_be_reviewed():
    assert rules.validate_ingredient_review("trigger", "r", False, [None, "ftp://x"])


def test_trigger_with_http_evidence_can_be_reviewed():
    assert rules.validate_ingredient_review("trigger", "r", False, ev()) == []


def test_major_allergen_cannot_be_suitable():
    errors = rules.validate_ingredient_review("suitable", None, True, [])
    assert any("九大過敏原" in e for e in errors)


def test_major_allergen_caution_ok():
    assert rules.validate_ingredient_review("caution", "常見過敏原", True, []) == []


def test_non_allergen_suitable_ok():
    assert rules.validate_ingredient_review("suitable", None, False, []) == []


def test_unrated_review_ok_without_evidence():
    assert rules.validate_ingredient_review("unrated", None, False, []) == []


def test_review_errors_accumulate():
    errors = rules.validate_ingredient_review("trigger", "", True, [])
    assert len(errors) == 2


def test_validate_evidence_ok():
    clean, errors = rules.validate_evidence(" T ", "https://a.org/x", "", "2020")
    assert errors == []
    assert clean == {"title": "T", "url": "https://a.org/x",
                     "source_type": "other", "year": 2020}


@pytest.mark.parametrize("title,url,year", [
    ("", "https://a.org", ""), ("t", "ftp://a.org", ""), ("t", "", ""),
    ("t", "https://a.org", "1700"), ("t", "https://a.org", "abc"),
    ("t", "https://a.org", "2101")])
def test_validate_evidence_rejects(title, url, year):
    clean, errors = rules.validate_evidence(title, url, "review", year)
    assert clean is None and errors


def test_parse_aliases():
    assert rules.parse_aliases("蛋, 雞蛋\n蛋，egg、蛋") == ["蛋", "雞蛋", "egg"]
    assert rules.parse_aliases(None) == []


@pytest.mark.parametrize("raw,expected", [
    ("", None), (" 85.5 ", 85.5), ("0", 0.0), ("100", 100.0)])
def test_parse_score_ok(raw, expected):
    assert rules.parse_score(raw) == (expected, [])


@pytest.mark.parametrize("raw", ["-1", "101", "abc", "nan", "inf"])
def test_parse_score_bad(raw):
    value, errors = rules.parse_score(raw)
    assert value is None and errors


def test_parse_positive_int():
    assert rules.parse_positive_int("", "x", 1) == (None, [])
    assert rules.parse_positive_int("30", "x", 0) == (30, [])
    assert rules.parse_positive_int("0", "x", 0) == (0, [])
    assert rules.parse_positive_int("0", "份量", 1)[1]
    assert rules.parse_positive_int("-3", "x", 0)[1]
    assert rules.parse_positive_int("1.5", "x", 0)[1]


M_OK = {"name_zh": "豬肉", "reviewed": True, "is_staple": False}


def test_publish_ok():
    assert rules.validate_publish([], [M_OK]) == []


def test_publish_blocked_by_unmatched():
    errors = rules.validate_publish(["香菜少許"], [M_OK])
    assert any("香菜少許" in e for e in errors)


def test_publish_blocked_by_unreviewed_ingredient():
    errors = rules.validate_publish([], [M_OK, {**M_OK, "name_zh": "蝦", "reviewed": False}])
    assert any("蝦" in e for e in errors)


def test_publish_needs_non_staple():
    assert rules.validate_publish([], [])
    assert rules.validate_publish([], [{**M_OK, "is_staple": True}])


def test_publish_collects_all_errors():
    assert len(rules.validate_publish(["x"], [{**M_OK, "reviewed": False, "is_staple": True}])) == 3


@pytest.mark.parametrize("current,action,ok", [
    ("pending_review", "publish", True), ("draft", "publish", True),
    ("published", "publish", False), ("rejected", "publish", False),
    ("pending_review", "reject", True), ("published", "reject", True),
    ("rejected", "reject", False),
    ("rejected", "resubmit", True), ("published", "resubmit", True),
    ("pending_review", "resubmit", False)])
def test_transitions(current, action, ok):
    assert (rules.check_transition(current, action) is None) is ok


def test_unknown_action_rejected():
    assert rules.check_transition("draft", "delete")


def test_merge_raw_text_and_remove_item():
    assert rules.merge_raw_text("香菜", "芫荽") == "香菜；芫荽"
    assert rules.merge_raw_text("香菜；芫荽", "芫荽") == "香菜；芫荽"
    assert rules.remove_item(["a", "b", "a"], "a") == ["b"]
