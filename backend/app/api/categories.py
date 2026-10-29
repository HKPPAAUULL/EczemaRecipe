from fastapi import APIRouter, HTTPException, Query, Request

from app import repository
from app.deps import db_conn, include_drafts
from app.schemas import (
    ALLOWED_RATINGS_FILTER,
    CategoryIngredientsResponse,
    CategoryItem,
)

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[CategoryItem])
def list_categories(request: Request):
    with db_conn(request) as conn:
        return repository.list_categories(conn, include_drafts(request))


@router.get("/{category_id}/ingredients", response_model=CategoryIngredientsResponse)
def category_ingredients(
    request: Request,
    category_id: int,
    rating: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    if rating is not None and rating not in ALLOWED_RATINGS_FILTER:
        raise HTTPException(
            status_code=422,
            detail=f"rating must be one of {sorted(ALLOWED_RATINGS_FILTER)}",
        )
    with db_conn(request) as conn:
        category = repository.get_category(conn, category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="category not found")
        total, items = repository.list_category_ingredients(
            conn, category_id, rating, limit, offset, include_drafts(request)
        )
    return {
        "category": category,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }
