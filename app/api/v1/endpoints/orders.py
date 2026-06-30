from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db.client import get_supabase_admin, get_supabase_for_token
from app.schemas.order import OrderCreate, OrderOut, OrderQuoteOut, OrderQuoteRequest
from app.services.order import OrderService
from supabase import Client

router = APIRouter(prefix="/orders", tags=["pedidos"])


def get_order_service(user: dict = Depends(get_current_user)) -> OrderService:
    db: Client = get_supabase_for_token(user["access_token"])
    return OrderService(db, write_db=get_supabase_admin())


@router.post("/quote", response_model=OrderQuoteOut)
async def quote_order(payload: OrderQuoteRequest):
    """Calcula frete estimado para o checkout do delivery."""
    return OrderService(db=None).quote(
        subtotal_cents=payload.subtotal_cents,
        free_delivery=payload.free_delivery,
    )


@router.post("/", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderCreate,
    user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Cria um novo pedido para o cliente autenticado."""
    return await service.create_order(profile_id=user["id"], payload=payload)


@router.get("/", response_model=list[OrderOut])
async def list_orders(
    page: int = 1,
    page_size: int = 20,
    user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Lista o historico de pedidos do cliente."""
    return await service.list_orders(
        profile_id=user["id"],
        page=page,
        page_size=page_size,
    )


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str,
    user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    return await service.get_order(order_id=order_id, profile_id=user["id"])


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: str,
    user: dict = Depends(get_current_user),
    service: OrderService = Depends(get_order_service),
):
    """Cancela um pedido (apenas nos status pending ou confirmed)."""
    return await service.cancel_order(order_id=order_id, profile_id=user["id"])
