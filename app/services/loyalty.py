from app.core.config import settings
from app.core.exceptions import InsufficientPointsError, NotFoundError
from app.schemas.loyalty import (
    LoyaltyAccountOut,
    LoyaltyTransactionOut,
    TransactionType,
)
from supabase import Client


class LoyaltyService:
    def __init__(self, db: Client, write_db: Client | None = None):
        self.db = db
        self.write_db = write_db or db

    def _get_account(self, profile_id: str) -> dict:
        resp = (
            self.db.table("loyalty_accounts")
            .select("*, loyalty_tiers(*)")
            .eq("profile_id", profile_id)
            .single()
            .execute()
        )
        if not resp.data:
            raise NotFoundError("Conta de fidelidade")
        return resp.data

    async def get_account(self, profile_id: str) -> LoyaltyAccountOut:
        data = self._get_account(profile_id)
        tier_data = data.pop("loyalty_tiers")
        return LoyaltyAccountOut(**data, tier=tier_data)

    async def earn_points(
        self,
        profile_id: str,
        order_id: str,
        order_total: int,
    ) -> int:
        """Credita pontos com base no total do pedido (em centavos)."""
        points = (order_total // 100) * settings.points_per_real
        if points <= 0:
            return 0

        existing = (
            self.db.table("loyalty_transactions")
            .select("id")
            .eq("order_id", order_id)
            .eq("type", TransactionType.EARN.value)
            .limit(1)
            .execute()
        )
        if existing.data:
            return 0

        account = self._get_account(profile_id)

        self.write_db.table("loyalty_accounts").update({
            "total_points": account["total_points"] + points,
            "available_points": account["available_points"] + points,
        }).eq("id", account["id"]).execute()

        self.write_db.table("loyalty_transactions").insert({
            "account_id": account["id"],
            "order_id": order_id,
            "type": TransactionType.EARN.value,
            "points": points,
            "description": f"Pontos ganhos no pedido #{order_id[:8]}",
        }).execute()

        await self._check_tier_upgrade(
            profile_id=profile_id,
            account=account,
            new_total=account["total_points"] + points,
        )

        return points

    async def reverse_points(self, order_id: str, profile_id: str) -> None:
        """Estorna os pontos de um pedido cancelado."""
        earn_tx = (
            self.db.table("loyalty_transactions")
            .select("*")
            .eq("order_id", order_id)
            .eq("type", TransactionType.EARN.value)
            .execute()
        )
        if not earn_tx.data:
            return

        points_to_reverse = sum(tx["points"] for tx in earn_tx.data)
        account = self._get_account(profile_id)

        new_available = max(0, account["available_points"] - points_to_reverse)
        self.write_db.table("loyalty_accounts").update({
            "available_points": new_available,
        }).eq("id", account["id"]).execute()

        self.write_db.table("loyalty_transactions").insert({
            "account_id": account["id"],
            "order_id": order_id,
            "type": TransactionType.REDEEM.value,
            "points": -points_to_reverse,
            "description": f"Estorno de pontos — pedido #{order_id[:8]} cancelado",
        }).execute()

    async def redeem_points(
        self,
        profile_id: str,
        points: int,
        description: str,
    ) -> None:
        """Resgata pontos disponíveis."""
        account = self._get_account(profile_id)

        if account["available_points"] < points:
            raise InsufficientPointsError(
                available=account["available_points"],
                required=points,
            )

        self.write_db.table("loyalty_accounts").update({
            "available_points": account["available_points"] - points,
        }).eq("id", account["id"]).execute()

        self.write_db.table("loyalty_transactions").insert({
            "account_id": account["id"],
            "type": TransactionType.REDEEM.value,
            "points": -points,
            "description": description,
        }).execute()

    async def list_transactions(
        self, profile_id: str, page: int = 1, page_size: int = 30
    ) -> list[LoyaltyTransactionOut]:
        account = self._get_account(profile_id)
        offset = (page - 1) * page_size

        resp = (
            self.db.table("loyalty_transactions")
            .select("*")
            .eq("account_id", account["id"])
            .order("created_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        return [LoyaltyTransactionOut(**tx) for tx in resp.data]

    async def _check_tier_upgrade(
        self,
        profile_id: str,
        account: dict,
        new_total: int,
    ) -> None:
        """Verifica e aplica upgrade de tier se necessário."""
        tiers_resp = (
            self.db.table("loyalty_tiers")
            .select("*")
            .lte("min_points", new_total)
            .order("min_points", desc=True)
            .limit(1)
            .execute()
        )
        if not tiers_resp.data:
            return

        new_tier = tiers_resp.data[0]
        if new_tier["id"] != account.get("tier_id"):
            self.write_db.table("loyalty_accounts").update({
                "tier_id": new_tier["id"],
            }).eq("id", account["id"]).execute()
