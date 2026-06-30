from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class OrderStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PREPARING = "preparing"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class PaymentMethod(StrEnum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    PIX = "pix"
    CASH = "cash"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentProvider(StrEnum):
    MANUAL = "manual"
    PIX_STATIC = "pix_static"
    MERCADO_PAGO = "mercado_pago"


class PaymentInstructions(BaseModel):
    title: str
    description: str
    method: PaymentMethod
    status: PaymentStatus
    pix_key: str | None = None
    pix_copy_paste: str | None = None
    amount: Decimal | None = None
    txid: str | None = None
    expires_at: datetime | None = None


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int
    customization: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Quantidade deve ser pelo menos 1")
        return v


class OrderCreate(BaseModel):
    address_id: UUID
    payment_method: PaymentMethod
    items: list[OrderItemCreate]
    promotion_code: str | None = None
    notes: str | None = None

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("O pedido deve ter pelo menos 1 item")
        return v


class OrderQuoteRequest(BaseModel):
    subtotal_cents: int = Field(default=0, ge=0)
    free_delivery: bool = False


class OrderQuoteOut(BaseModel):
    subtotal_cents: int
    delivery_fee_cents: int
    free_delivery_threshold_cents: int
    amount_to_free_delivery_cents: int


class OrderItemOut(BaseModel):
    id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal
    customization: str | None


class OrderOut(BaseModel):
    id: UUID
    status: OrderStatus
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    payment_provider: PaymentProvider = PaymentProvider.MANUAL
    payment_reference: str | None = None
    payment_instructions: PaymentInstructions | None = None
    subtotal: Decimal
    delivery_fee: Decimal
    discount: Decimal
    total: Decimal
    notes: str | None
    placed_at: datetime
    delivered_at: datetime | None
    paid_at: datetime | None = None
    items: list[OrderItemOut] = []
