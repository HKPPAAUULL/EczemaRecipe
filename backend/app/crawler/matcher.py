"""Deterministic ingredient matching: exact name/alias hit, else the single
longest known-name token contained in the item text. Multiple distinct
ingredient hits at the same max length → ambiguous → unmatched (never guess).
"""

from __future__ import annotations

from app.crawler.parse import normalize


class IngredientMatcher:
    def __init__(self, names: dict[str, int]):
        """names: normalized known name -> ingredient_id."""
        self._map = dict(names)

    @classmethod
    def from_rows(cls, rows) -> IngredientMatcher:
        """rows: iterable of (ingredient_id, name_zh, aliases)."""
        names: dict[str, int] = {}
        for iid, name_zh, aliases in rows:
            for n in (name_zh, *(aliases or [])):
                key = normalize(n)
                if key and key not in names:
                    names[key] = iid
        return cls(names)

    def match(self, item_name: str) -> int | None:
        """ingredient_id or None (no hit or ambiguous)."""
        key = normalize(item_name)
        if not key:
            return None
        if key in self._map:
            return self._map[key]
        hits: dict[int, str] = {}
        for known, iid in self._map.items():
            if (
                len(known) >= 2
                and known in key
                and (iid not in hits or len(known) > len(hits[iid]))
            ):
                hits[iid] = known
        if not hits:
            return None
        best = max(len(v) for v in hits.values())
        winners = {iid for iid, v in hits.items() if len(v) == best}
        return winners.pop() if len(winners) == 1 else None
