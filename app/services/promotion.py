from datetime import UTC, datetime
from uuid import UUID

from app.core.exceptions import PromotionExpiredError, PromotionLimitReachedError
from app.schemas.loyalty import (
    PromotionAvailableOut,
    PromotionType,
    PromotionValidateResponse,
)
from supabase import Client


class PromotionService:
    def __init__(self, db: Client, write_db: Client | None = None):
        self.db = db
        self.write_db = write_db or db

    async def list_available(
        self,
        tier_name: str | None = None,
    ) -> list[PromotionAvailableOut]:
        resp = (
            self.db.table("promotions")
            .select("*")
            .eq("active", True)
            .order("created_at", desc=True)
            .execute()
        )

        now = datetime.now(tz=UTC)
        audience = (
            f"Disponivel para seu nivel {tier_name}"
            if tier_name
            else "Disponivel para clientes autenticados"
        )
        promotions: list[PromotionAvailableOut] = []

        for promo in resp.data or []:
            starts_at = self._parse_datetime(promo.get("starts_at"))
            expires_at = self._parse_datetime(promo.get("expires_at"))
            max_uses = promo.get("max_uses")
            uses_count = promo.get("uses_count") or 0

            if starts_at and starts_at > now:
                continue
            if expires_at and expires_at < now:
                continue
            if max_uses and uses_count >= max_uses:
                continue

            promotions.append(
                PromotionAvailableOut(
                    id=UUID(promo["id"]),
                    code=promo["code"],
                    description=promo.get("description"),
                    type=PromotionType(promo["type"]),
                    value=promo["value"],
                    min_order_cents=promo.get("min_order_cents") or 0,
                    expires_at=expires_at,
                    audience=audience,
                )
            )

        return promotions

    async def validate(
        self,
        code: str,
        profile_id: str,
        order_subtotal: int,
    ) -> PromotionValidateResponse:
        resp = (
            self.db.table("promotions")
            .select("*")
            .eq("code", code.upper())
            .eq("active", True)
            .single()
            .execute()
        )

        if not resp.data:
            return PromotionValidateResponse(valid=False, description="Cupom invalido")

        promo = resp.data
        now = datetime.now(tz=UTC)

        if promo["starts_at"] and datetime.fromisoformat(promo["starts_at"]) > now:
            raise PromotionExpiredError()
        if promo["expires_at"] and datetime.fromisoformat(promo["expires_at"]) < now:
            raise PromotionExpiredError()

        if promo["max_uses"] and promo["uses_count"] >= promo["max_uses"]:
            raise PromotionLimitReachedError()

        used = (
            self.db.table("promotion_usages")
            .select("id")
            .eq("promotion_id", promo["id"])
            .eq("profile_id", profile_id)
            .execute()
        )
        if used.data:
            return PromotionValidateResponse(
                valid=False,
                description="Cupom ja utilizado",
            )

        if promo["min_order_cents"] and order_subtotal < promo["min_order_cents"]:
            min_fmt = f"R$ {promo['min_order_cents'] / 100:.2f}"
            return PromotionValidateResponse(
                valid=False,
                description=f"Pedido minimo de {min_fmt} para usar este cupom",
            )

        discount = self._calculate_discount(promo, order_subtotal)

        return PromotionValidateResponse(
            valid=True,
            promotion_id=UUID(promo["id"]),
            type=PromotionType(promo["type"]),
            discount=discount,
            description=f"Cupom {code.upper()} aplicado com sucesso",
        )

    def _calculate_discount(self, promo: dict, subtotal: int) -> int:
        match promo["type"]:
            case PromotionType.PERCENTAGE:
                return int(subtotal * promo["value"] / 100)
            case PromotionType.FIXED:
                return min(int(promo["value"] * 100), subtotal)
            case PromotionType.FREE_DELIVERY:
                return 0
            case _:
                return 0

    def _parse_datetime(self, value: str | datetime | None) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    async def register_usage(
        self,
        promotion_id: UUID,
        profile_id: str,
        order_id: str,
        discount_applied: float,
    ) -> None:
        self.write_db.table("promotion_usages").insert(
            {
                "promotion_id": str(promotion_id),
                "profile_id": profile_id,
                "order_id": order_id,
                "discount_applied": discount_applied,
            }
        ).execute()

        self.write_db.rpc(
            "increment_promotion_uses",
            {"promo_id": str(promotion_id)},
        ).execute()
