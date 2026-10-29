"""Pydantic response models and shared constants for the read API."""

from datetime import datetime

from pydantic import BaseModel

RATING_LABELS = {
    "suitable": "一般適合",
    "caution": "因人而異",
    "trigger": "常見誘發",
    "unrated": "資料不足",
}

# ratings accepted by the ?rating= filter (mirrors the eczema_rating enum)
ALLOWED_RATINGS_FILTER = set(RATING_LABELS)

DISCLAIMER = "本站資訊僅供參考，不能取代醫生或營養師意見。"


class CategoryRef(BaseModel):
    id: int
    name_zh: str


class IngredientListItem(BaseModel):
    id: int
    name_zh: str
    name_en: str | None
    category: CategoryRef | None
    eczema_rating: str
    rating_label: str
    allergens: list[str]
    draft: bool


class SearchResponse(BaseModel):
    query: str
    count: int
    items: list[IngredientListItem]


class AllergenItem(BaseModel):
    id: int
    name_zh: str
    name_en: str | None
    type: str


class IngredientAllergen(BaseModel):
    id: int
    name_zh: str
    type: str
    severity: str | None


class EvidenceItem(BaseModel):
    title: str
    url: str | None
    source_type: str
    year: int | None


class NutrientItem(BaseModel):
    name: str
    unit: str
    amount_per_100g: float
    source: str | None


class IngredientDetail(BaseModel):
    id: int
    name_zh: str
    name_en: str | None
    aliases: list[str]
    category: CategoryRef | None
    eczema_rating: str
    rating_label: str
    rating_reason: str | None
    allergens: list[IngredientAllergen]
    evidence: list[EvidenceItem]
    nutrients: list[NutrientItem]
    needs_senior_review: bool | None = None
    draft: bool
    disclaimer: str = DISCLAIMER
    updated_at: datetime | None


class CategoryItem(BaseModel):
    id: int
    name_zh: str
    sort_order: int
    ingredient_count: int


class CategoryIngredientsResponse(BaseModel):
    category: CategoryRef
    total: int
    limit: int
    offset: int
    items: list[IngredientListItem]
