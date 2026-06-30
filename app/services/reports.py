from collections import defaultdict
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from app.schemas.admin import (
    AdminReportsOut,
    CouponUsageOut,
    CustomerRecurrenceOut,
    ProductSalesOut,
    ReportSummaryOut,
)
from supabase import Client


class ReportService:
    def __init__(self, db: Client):
        self.db = db

    async def get_admin_reports(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> AdminReportsOut:
        orders = self._rows("orders", "*, order_items(*)")
        products = {item["id"]: item for item in self._rows("products", "*")}
        profiles = {item["id"]: item for item in self._rows("profiles", "*")}
        promotions = {item["id"]: item for item in self._rows("promotions", "*")}
        usages = self._rows("promotion_usages", "*")

        period_orders = [
            order
            for order in orders
            if self._in_period(order.get("placed_at"), date_from, date_to)
        ]
        billable_orders = [
            order for order in period_orders if order.get("status") != "cancelled"
        ]

        return AdminReportsOut(
            summary=self._summary(period_orders, billable_orders, date_from, date_to),
            top_products=self._top_products(billable_orders, products),
            recurring_customers=self._recurring_customers(billable_orders, profiles),
            coupon_usage=self._coupon_usage(usages, promotions, date_from, date_to),
        )

    def _rows(self, table: str, select: str) -> list[dict[str, Any]]:
        response = self.db.table(table).select(select).execute()
        return response.data or []

    def _summary(
        self,
        period_orders: list[dict[str, Any]],
        billable_orders: list[dict[str, Any]],
        date_from: date | None,
        date_to: date | None,
    ) -> ReportSummaryOut:
        gross_revenue = sum(
            (self._decimal(order.get("subtotal")) for order in billable_orders),
            Decimal("0"),
        )
        net_revenue = sum(
            (self._decimal(order.get("total")) for order in billable_orders),
            Decimal("0"),
        )
        discount_total = sum(
            (self._decimal(order.get("discount")) for order in billable_orders),
            Decimal("0"),
        )
        delivery_fee_total = sum(
            (self._decimal(order.get("delivery_fee")) for order in billable_orders),
            Decimal("0"),
        )
        orders_count = len(billable_orders)

        return ReportSummaryOut(
            start_date=date_from,
            end_date=date_to,
            gross_revenue=gross_revenue,
            net_revenue=net_revenue,
            orders_count=orders_count,
            delivered_orders_count=sum(
                1 for order in period_orders if order.get("status") == "delivered"
            ),
            cancelled_orders_count=sum(
                1 for order in period_orders if order.get("status") == "cancelled"
            ),
            average_ticket=(
                net_revenue / Decimal(orders_count)
                if orders_count
                else Decimal("0")
            ),
            coupon_discount_total=discount_total,
            delivery_fee_total=delivery_fee_total,
        )

    def _top_products(
        self,
        orders: list[dict[str, Any]],
        products: dict[str, dict[str, Any]],
    ) -> list[ProductSalesOut]:
        grouped = {}
        order_sets = defaultdict(set)

        for order in orders:
            order_id = order.get("id")
            for item in order.get("order_items") or []:
                product_id = str(item.get("product_id") or "")
                if not product_id:
                    continue
                quantity = int(item.get("quantity") or 0)
                revenue = self._decimal(item.get("unit_price")) * Decimal(quantity)
                current = grouped.setdefault(
                    product_id,
                    {
                        "quantity_sold": 0,
                        "revenue": Decimal("0"),
                    },
                )
                current["quantity_sold"] += quantity
                current["revenue"] += revenue
                if order_id:
                    order_sets[product_id].add(order_id)

        rows = []
        for product_id, metrics in grouped.items():
            product = products.get(product_id, {})
            rows.append(
                ProductSalesOut(
                    product_id=product_id,
                    product_name=product.get("name") or f"Produto {product_id[:8]}",
                    category=product.get("category"),
                    quantity_sold=metrics["quantity_sold"],
                    orders_count=len(order_sets[product_id]),
                    revenue=metrics["revenue"],
                )
            )

        return sorted(rows, key=lambda item: item.revenue, reverse=True)[:10]

    def _recurring_customers(
        self,
        orders: list[dict[str, Any]],
        profiles: dict[str, dict[str, Any]],
    ) -> list[CustomerRecurrenceOut]:
        grouped = {}
        for order in orders:
            profile_id = str(order.get("profile_id") or "")
            if not profile_id:
                continue
            current = grouped.setdefault(
                profile_id,
                {
                    "orders_count": 0,
                    "total_spent": Decimal("0"),
                    "last_order_at": None,
                },
            )
            current["orders_count"] += 1
            current["total_spent"] += self._decimal(order.get("total"))
            current["last_order_at"] = self._max_datetime(
                current["last_order_at"],
                self._parse_datetime(order.get("placed_at")),
            )

        rows = []
        for profile_id, metrics in grouped.items():
            if metrics["orders_count"] < 2:
                continue
            profile = profiles.get(profile_id, {})
            rows.append(
                CustomerRecurrenceOut(
                    profile_id=profile_id,
                    full_name=profile.get("full_name"),
                    email=profile.get("email"),
                    phone=profile.get("phone"),
                    orders_count=metrics["orders_count"],
                    total_spent=metrics["total_spent"],
                    average_ticket=metrics["total_spent"]
                    / Decimal(metrics["orders_count"]),
                    last_order_at=metrics["last_order_at"],
                )
            )

        return sorted(rows, key=lambda item: item.total_spent, reverse=True)[:10]

    def _coupon_usage(
        self,
        usages: list[dict[str, Any]],
        promotions: dict[str, dict[str, Any]],
        date_from: date | None,
        date_to: date | None,
    ) -> list[CouponUsageOut]:
        grouped = {}
        for usage in usages:
            if not self._in_period(usage.get("used_at"), date_from, date_to):
                continue
            promotion_id = str(usage.get("promotion_id") or "")
            if not promotion_id:
                continue
            current = grouped.setdefault(
                promotion_id,
                {"uses_count": 0, "total_discount": Decimal("0")},
            )
            current["uses_count"] += 1
            current["total_discount"] += self._decimal(usage.get("discount_applied"))

        rows = []
        for promotion_id, metrics in grouped.items():
            promotion = promotions.get(promotion_id, {})
            rows.append(
                CouponUsageOut(
                    promotion_id=promotion_id,
                    code=promotion.get("code") or f"Cupom {promotion_id[:8]}",
                    description=promotion.get("description"),
                    uses_count=metrics["uses_count"],
                    total_discount=metrics["total_discount"],
                )
            )

        return sorted(rows, key=lambda item: item.uses_count, reverse=True)[:10]

    def _in_period(
        self,
        value: str | datetime | None,
        date_from: date | None,
        date_to: date | None,
    ) -> bool:
        parsed = self._parse_datetime(value)
        if not parsed:
            return date_from is None and date_to is None
        if date_from and parsed < datetime.combine(date_from, time.min, tzinfo=UTC):
            return False
        if date_to and parsed > datetime.combine(date_to, time.max, tzinfo=UTC):
            return False
        return True

    def _parse_datetime(self, value: str | datetime | None) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _max_datetime(
        self,
        current: datetime | None,
        candidate: datetime | None,
    ) -> datetime | None:
        if not current:
            return candidate
        if not candidate:
            return current
        return max(current, candidate)

    def _decimal(self, value: Any) -> Decimal:
        return Decimal(str(value or "0"))
