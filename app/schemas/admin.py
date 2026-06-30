from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.loyalty import PromotionType
from app.schemas.order import OrderStatus, PaymentStatus

AdminRole = Literal["owner", "manager", "staff"]


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    category: str = "cafeteria"
    price: Decimal = Field(ge=0)
    available: bool = True
    image_url: str | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    available: bool | None = None
    image_url: str | None = None


class ProductOut(ProductCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class AdminUserCreate(BaseModel):
    profile_id: UUID
    role: AdminRole = "staff"
    active: bool = True


class AdminUserUpdate(BaseModel):
    role: AdminRole | None = None
    active: bool | None = None


class AdminUserOut(BaseModel):
    id: UUID
    profile_id: UUID
    email: str | None = None
    full_name: str | None = None
    role: AdminRole
    active: bool
    created_at: datetime
    updated_at: datetime


class CustomerUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: date | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        digits = "".join(filter(str.isdigit, value))
        if len(digits) not in (10, 11):
            raise ValueError("Telefone deve ter 10 ou 11 digitos")
        return digits


class CustomerOut(BaseModel):
    id: UUID
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: date | None = None
    created_at: datetime
    updated_at: datetime


class PromotionCreate(BaseModel):
    code: str
    description: str | None = None
    type: PromotionType
    value: Decimal = Field(default=0, ge=0)
    min_order_cents: int = Field(default=0, ge=0)
    max_uses: int | None = Field(default=None, gt=0)
    active: bool = True
    starts_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class PromotionUpdate(BaseModel):
    code: str | None = None
    description: str | None = None
    type: PromotionType | None = None
    value: Decimal | None = Field(default=None, ge=0)
    min_order_cents: int | None = Field(default=None, ge=0)
    max_uses: int | None = Field(default=None, gt=0)
    active: bool | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip().upper()


class PromotionOut(PromotionCreate):
    id: UUID
    uses_count: int
    created_at: datetime
    updated_at: datetime


class AdminOrderUpdate(BaseModel):
    status: OrderStatus | None = None
    payment_status: PaymentStatus | None = None
    delivered_at: datetime | None = None
    notes: str | None = None


class AuditLogOut(BaseModel):
    id: UUID
    actor_profile_id: UUID | None = None
    actor_email: str | None = None
    actor_role: str | None = None
    auth_method: str | None = None
    action: str
    entity_type: str
    entity_id: str | None = None
    before_data: dict[str, Any] | None = None
    after_data: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReportSummaryOut(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    gross_revenue: Decimal
    net_revenue: Decimal
    orders_count: int
    delivered_orders_count: int
    cancelled_orders_count: int
    average_ticket: Decimal
    coupon_discount_total: Decimal
    delivery_fee_total: Decimal


class ProductSalesOut(BaseModel):
    product_id: str
    product_name: str
    category: str | None = None
    quantity_sold: int
    orders_count: int
    revenue: Decimal


class CustomerRecurrenceOut(BaseModel):
    profile_id: str
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    orders_count: int
    total_spent: Decimal
    average_ticket: Decimal
    last_order_at: datetime | None = None


class CouponUsageOut(BaseModel):
    promotion_id: str
    code: str
    description: str | None = None
    uses_count: int
    total_discount: Decimal


class AdminReportsOut(BaseModel):
    summary: ReportSummaryOut
    top_products: list[ProductSalesOut]
    recurring_customers: list[CustomerRecurrenceOut]
    coupon_usage: list[CouponUsageOut]
