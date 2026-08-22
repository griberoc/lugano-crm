from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.core.exceptions import NotFoundError
from app.schemas.order import OrderStatus
from app.services.delivery import DeliveryService
from app.services.loyalty import LoyaltyService
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)


class OrderLifecycleService:
    """Aplica os efeitos do pedido somente depois das transicoes corretas."""

    def __init__(self, db):
        self.db = db
        self.loyalty = LoyaltyService(db)
        self.delivery = DeliveryService(db)
        self.notifications = NotificationService(db)

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        response = (
            self.db.table("orders")
            .select("*, order_items(*)")
            .eq("id", order_id)
            .single()
            .execute()
        )
        return response.data or None

    async def payment_approved(self, order_id: str) -> dict[str, Any] | None:
        order = self.get_order(order_id)
        if not order or order.get("payment_status") != "paid":
            return order

        if order.get("status") == OrderStatus.PENDING.value:
            response = (
                self.db.table("orders")
                .update({"status": OrderStatus.CONFIRMED.value})
                .eq("id", order_id)
                .eq("status", OrderStatus.PENDING.value)
                .execute()
            )
            if response.data:
                order.update(response.data[0])
                await self.notifications.safe_notify_order_status(order)

        await self._credit_loyalty(order)
        return order

    async def order_delivered(self, order_id: str) -> dict[str, Any] | None:
        order = self.get_order(order_id)
        if not order or order.get("payment_status") != "paid":
            return order
        await self._credit_loyalty(order)
        return order

    async def dispatch_paid_order(self, order_id: str):
        order = self.get_order(order_id)
        if not order:
            return None
        profile_id = order.get("profile_id")
        address_id = order.get("address_id")
        customer = self._single("profiles", "id", profile_id)
        address = self._single("addresses", "id", address_id)
        items = order.get("order_items") or []
        return await self.delivery.safe_dispatch_order(
            order=order,
            customer=customer,
            address=address,
            items=items,
        )

    async def _credit_loyalty(self, order: dict[str, Any]) -> int:
        total_cents = int(Decimal(str(order.get("total") or 0)) * 100)
        try:
            return await self.loyalty.earn_points(
                profile_id=str(order["profile_id"]),
                order_id=str(order["id"]),
                order_total=total_cents,
            )
        except NotFoundError:
            logger.warning(
                "Loyalty account missing while processing order_id=%s",
                order.get("id"),
            )
            return 0

    def _single(self, table: str, field: str, value: Any) -> dict | None:
        if value is None:
            return None
        response = (
            self.db.table(table).select("*").eq(field, value).single().execute()
        )
        return response.data or None
