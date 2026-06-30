from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


# ── Fidelidade ────────────────────────────────────────────────────────────────

class LoyaltyTierOut(BaseModel):
    id: UUID
    name: str
    min_points: int
    cashback_rate: Decimal
    benefits: dict


class LoyaltyAccountOut(BaseModel):
    id: UUID
    total_points: int
    available_points: int
    tier: LoyaltyTierOut


class TransactionType(StrEnum):
    EARN = "earn"
    REDEEM = "redeem"
    EXPIRE = "expire"
    BONUS = "bonus"


class LoyaltyTransactionOut(BaseModel):
    id: UUID
    type: TransactionType
    points: int
    description: str
    created_at: datetime


# ── Promoções ─────────────────────────────────────────────────────────────────

class PromotionType(StrEnum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    FREE_DELIVERY = "free_delivery"


class PromotionValidateRequest(BaseModel):
    code: str
    order_subtotal: int  # em centavos


class PromotionValidateResponse(BaseModel):
    valid: bool
    promotion_id: UUID | None = None
    type: PromotionType | None = None
    discount: int = 0          # em centavos
    description: str = ""


class PromotionAvailableOut(BaseModel):
    id: UUID
    code: str
    description: str | None = None
    type: PromotionType
    value: Decimal
    min_order_cents: int = 0
    expires_at: datetime | None = None
    audience: str
