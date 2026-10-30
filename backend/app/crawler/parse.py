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
_FRACTION_RE = re.compile(r"^(\d+)\s*/\s*(\d+)$")
_PAREN_RE = re.compile(r"[（(][^）)]*[）)]")
_QTY_TOKEN = (
    r"(\d+\s*/\s*\d+|\d+(?:\.\d+)?(?:\s*[-–~]\s*\d+(?:\.\d+)?)?|"
    r"[一二三四五六七八九]?十[一二三四五六七八九]?|[一二三四五六七八九兩半])"
)
# units observed in the hakka dataset; used to split qty-first items like
# 「1/2醋匙」→ 醋 1/2 匙. Anything we cannot decompose stays unmatched.
_UNIT_SUFFIXES = (
    "大匙", "湯匙", "茶匙", "小匙", "毫升", "公克", "大碗", "小撮",
    "斤", "兩", "克", "碗", "杯", "鍋", "個", "顆", "粒", "支", "朵",
    "條", "片", "塊", "株", "把", "副", "隻", "張", "包", "根", "盒",
    "付", "匙", "g", "ml", "cc", "撮", "段", "盒", "瓶",
)
_UNIT_SUFFIX_RE = re.compile(
    f"(?:{'|'.join(sorted(_UNIT_SUFFIXES, key=len, reverse=True))})$")


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


def _qty_value(qtytok: str) -> float | None:
    fm = _FRACTION_RE.match(qtytok)
    if fm:
        return float(fm.group(1)) / float(fm.group(2))
    if re.fullmatch(r"\d+(?:\.\d+)?", qtytok):
        return float(qtytok)
    if re.search(r"[-–~]", qtytok):
        return None
    return _cn_number(qtytok)


def parse_item(text: str) -> ParsedItem:
    raw = text.strip().rstrip("。．、")
    body = _PAREN_RE.sub("", raw).strip() or raw
    # qty-first: leading arabic digit, e.g. 「1/2醋匙」→ 醋 1/2 匙 or
    # 「3根香蕉」→ 香蕉 3 根. Chinese-numeral-led items are treated as names
    # (九層塔/五花肉) — guessing is worse than leaving them unmatched.
    if body[0].isdigit():
        m2 = re.match(_QTY_TOKEN, body)
        if m2:
            qtytok, tail = m2.group(1), body[m2.end():].strip()
            qty = _qty_value(qtytok)
            pm = re.match(
                f"(?:{'|'.join(sorted(_UNIT_SUFFIXES, key=len, reverse=True))})",
                tail)
            if pm and len(tail[pm.end():]) >= 1:  # qty+unit+name
                return ParsedItem(raw, tail[pm.end():], qty, pm.group(0))
            um = _UNIT_SUFFIX_RE.search(tail)
            if um and len(tail[: um.start()]) >= 1:  # qty+name+unit
                return ParsedItem(raw, tail[: um.start()], qty, um.group(0))
            return ParsedItem(raw, tail or body, qty, None)
    # name-first: first arabic digit splits name from qty+unit
    md = re.search(r"\d", body)
    if md:
        name = body[: md.start()].strip()
        rest = body[md.start():].strip()
        m2 = re.match(_QTY_TOKEN, rest)
        qtytok = m2.group(1) if m2 else ""
        unit = rest[m2.end():].strip() if m2 else rest
        return ParsedItem(raw, name or body, _qty_value(qtytok), unit or None)
    # Chinese-numeral qty only when the tail is a unit （豬肚一副/香蕉三根）
    for mm in re.finditer(r"[一二三四五六七八九十半兩]", body[1:]):
        pos = mm.start() + 1
        m2 = re.match(_QTY_TOKEN, body[pos:])
        if not m2:
            continue
        tail = body[pos + m2.end():].strip()
        if not tail or _UNIT_SUFFIX_RE.fullmatch(tail) or tail in _NO_QTY_UNITS:
            return ParsedItem(
                raw, body[:pos].strip(), _qty_value(m2.group(1)), tail or None)
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
