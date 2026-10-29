from fastapi import APIRouter, Request

from app import repository
from app.deps import db_conn
from app.schemas import AllergenItem

router = APIRouter(prefix="/api/allergens", tags=["allergens"])


@router.get("", response_model=list[AllergenItem])
def list_allergens(request: Request):
    with db_conn(request) as conn:
        return repository.list_allergens(conn)
