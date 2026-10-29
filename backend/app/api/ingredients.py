from fastapi import APIRouter, HTTPException, Query, Request

from app import repository
from app.deps import db_conn, include_drafts
from app.schemas import IngredientDetail, SearchResponse

router = APIRouter(prefix="/api/ingredients", tags=["ingredients"])


@router.get("/search", response_model=SearchResponse)
def search(
    request: Request,
    q: str = Query(...),
    limit: int = Query(20, ge=1, le=50),
):
    q = q.strip()
    if not 1 <= len(q) <= 50:
        raise HTTPException(status_code=422, detail="q must be 1-50 characters")
    with db_conn(request) as conn:
        items = repository.search_ingredients(conn, q, limit, include_drafts(request))
    return {"query": q, "count": len(items), "items": items}


@router.get("/{ingredient_id}", response_model=IngredientDetail)
def detail(request: Request, ingredient_id: int):
    with db_conn(request) as conn:
        item = repository.get_ingredient_detail(
            conn, ingredient_id, include_drafts(request)
        )
    if item is None:
        raise HTTPException(status_code=404, detail="ingredient not found")
    return item
