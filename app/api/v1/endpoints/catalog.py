from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.db.client import get_supabase
from app.schemas.catalog import CatalogProductOut

router = APIRouter(prefix="/catalog", tags=["catalogo"])


@router.get("/products", response_model=list[CatalogProductOut])
async def list_catalog_products(
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Client = Depends(get_supabase),
):
    offset = (page - 1) * page_size
    query = db.table("products").select("*").eq("available", True)
    if category:
        query = query.eq("category", category)
    response = (
        query.order("category")
        .order("name")
        .range(offset, offset + page_size - 1)
        .execute()
    )
    return response.data
