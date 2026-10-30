"""Split Hakka `practic` text into structured ingredient items.

Format: ``1、材料：<items>。2、調味料：<items>。3、步驟：<steps>``.
Steps are never stored (PLAN.md §4.3: no full-text copying).
Each item: ``<name><qty?><unit?>`` — qty may be arabic, fraction ``1/2``,
range ``3-5``, or Chinese numeral ``一/半/十``; unit words like 少許/適量
count as unit with qty NULL.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_CN_DIGIT = {
    "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9,
}
_NO_QTY_UNITS = {"少許", "適量", "酌量", "些許"}
_SECTION_RE = re.compile(
    r"材料\s*[:：](?P<mat>.+?)\s*[。．]?\s*2\s*[、.．]?\s*"
    r"調味料\s*[:：](?P<sea>.*?)\s*[。．]?\s*3\s*[、.．]?\s*步驟",
    re.DOTALL,
)
_QTY_START = re.compile(r"[\d一二三四五六七八九十半兩]")
_FRACTION_RE = re.compile(r"^(\d+)\s*/\s*(\d+)$")
_PAREN_RE = re.compile(r"[（(][^）)]*[）)]")


def normalize(s: str | None) -> str:
    return "".join(unicodedata.normalize("NFKC", s or "").split())


def _cn_number(tok: str) -> float | None:
    if tok == "半":
        return 0.5
    if tok in _CN_DIGIT:
        return float(_CN_DIGIT[tok])
    if tok == "十":
        return 10.0
    m = re.fullmatch(r"十([一二三四五六七八九])", tok)
    if m:
        return 10.0 + _CN_DIGIT[m.group(1)]
    m = re.fullmatch(r"([一二三四五六七八九])十([一二三四五六七八九])?", tok)
    if m:
        return _CN_DIGIT[m.group(1)] * 10.0 + (_CN_DIGIT[m.group(2)] if m.group(2) else 0)
    return None


@dataclass
class ParsedItem:
    raw_text: str
    name: str
    qty: float | None
    unit: str | None


@dataclass
class ParsedRecipe:
    materials: list[ParsedItem] = field(default_factory=list)
    seasonings: list[ParsedItem] = field(default_factory=list)

    @property
    def items(self) -> list[ParsedItem]:
        return [*self.materials, *self.seasonings]


def parse_item(text: str) -> ParsedItem:
    raw = text.strip().rstrip("。．、")
    body = _PAREN_RE.sub("", raw).strip() or raw
    m = _QTY_START.search(body)
    if m:
        name = body[: m.start()].strip()
        rest = body[m.start():].strip()
        m2 = re.match(
            r"(\d+\s*/\s*\d+|"
            r"\d+(?:\.\d+)?(?:\s*[-–~]\s*\d+(?:\.\d+)?)?|"
            r"[一二三四五六七八九]?十[一二三四五六七八九]?|[一二三四五六七八九兩半])",
            rest,
        )
        qtytok, unit = (m2.group(1) if m2 else ""), rest[m2.end():].strip() if m2 else rest
        qty: float | None = None
        if _FRACTION_RE.match(qtytok):
            a, b = _FRACTION_RE.match(qtytok).groups()  # type: ignore[union-attr]
            qty = float(a) / float(b)
        elif re.fullmatch(r"\d+(?:\.\d+)?", qtytok):
            qty = float(qtytok)
        elif re.search(r"[-–~]", qtytok):
            qty = None  # range — keep raw_text only
        else:
            qty = _cn_number(qtytok)
        return ParsedItem(raw, name or body, qty, unit or None)
    for u in _NO_QTY_UNITS:
        if body.endswith(u) and len(body) > len(u):
            return ParsedItem(raw, body[: -len(u)].strip(), None, u)
    return ParsedItem(raw, body, None, None)


def _split_items(section: str) -> list[ParsedItem]:
    out = []
    for part in re.split(r"[、,，；;]", section or ""):
        if part.strip().rstrip("。．"):
            out.append(parse_item(part))
    return out


def parse_practic(text: str) -> ParsedRecipe | None:
    """Parse the practic blob; None when 材料/調味料 markers are absent."""
    m = _SECTION_RE.search(text or "")
    if not m:
        return None
    return ParsedRecipe(
        materials=_split_items(m.group("mat")),
        seasonings=_split_items(m.group("sea")),
    )
