from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.db.client import get_supabase_for_token
from app.schemas.loyalty import (
    LoyaltyAccountOut,
    LoyaltyTransactionOut,
    PromotionAvailableOut,
    PromotionValidateRequest,
    PromotionValidateResponse,
)
from app.services.loyalty import LoyaltyService
from app.services.promotion import PromotionService
from supabase import Client

router = APIRouter(tags=["fidelidade e promocoes"])

loyalty_router = APIRouter(prefix="/loyalty")
promotion_router = APIRouter(prefix="/promotions")


def get_authenticated_db(user: dict = Depends(get_current_user)) -> Client:
    return get_supabase_for_token(user["access_token"])


@loyalty_router.get("/", response_model=LoyaltyAccountOut)
async def get_loyalty_account(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    """Retorna saldo de pontos e tier atual do cliente."""
    return await LoyaltyService(db).get_account(user["id"])


@loyalty_router.get("/transactions", response_model=list[LoyaltyTransactionOut])
async def list_transactions(
    page: int = 1,
    page_size: int = 30,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    """Extrato de pontos do cliente."""
    return await LoyaltyService(db).list_transactions(
        profile_id=user["id"], page=page, page_size=page_size
    )


@promotion_router.post("/validate", response_model=PromotionValidateResponse)
async def validate_promotion(
    payload: PromotionValidateRequest,
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    """Valida um cupom e retorna o desconto aplicavel antes de fechar o pedido."""
    return await PromotionService(db).validate(
        code=payload.code,
        profile_id=user["id"],
        order_subtotal=payload.order_subtotal,
    )


@promotion_router.get("/available", response_model=list[PromotionAvailableOut])
async def list_available_promotions(
    user: dict = Depends(get_current_user),
    db: Client = Depends(get_authenticated_db),
):
    """Lista promocoes ativas disponiveis para o painel do cliente."""
    loyalty = await LoyaltyService(db).get_account(user["id"])
    return await PromotionService(db).list_available(tier_name=loyalty.tier.name)


router.include_router(loyalty_router)
router.include_router(promotion_router)
