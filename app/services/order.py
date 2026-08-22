import logging
from datetime import UTC, datetime
from decimal import Decimal

from app.core.config import settings
from app.core.exceptions import NotFoundError, UnprocessableError
from app.schemas.order import OrderCreate, OrderOut, OrderQuoteOut, OrderStatus
from app.services.delivery import DeliveryService
from app.services.loyalty import LoyaltyService
from app.services.notification import NotificationService
from app.services.order_lifecycle import OrderLifecycleService
from app.services.payment import PaymentProviderError, PaymentService
from app.services.promotion import PromotionService
from supabase import Client

logger = logging.getLogger("lugano.orders")


class OrderService:
    def __init__(self, db: Client, write_db: Client | None = None):
        self.db = db
        self.write_db = write_db or db
        self.loyalty = LoyaltyService(db, write_db=self.write_db)
        self.notifications = NotificationService(self.write_db)
        self.promotion = PromotionService(db, write_db=self.write_db)
        self.payments = PaymentService()
        self.delivery = DeliveryService(self.write_db)

    def _to_order_out(self, data: dict) -> OrderOut:
        data = data.copy()
        data["items"] = data.pop("order_items", data.get("items", []))
        data["payment_instructions"] = data.get("payment_payload") or None
        return OrderOut(**data)

    def _get_customer(self, profile_id: str) -> dict | None:
        try:
            response = (
                self.write_db.table("profiles")
                .select("id, full_name, email, phone")
                .eq("id", profile_id)
                .single()
                .execute()
            )
            return response.data or None
        except Exception:
            return None

    def quote(self, subtotal_cents: int, free_delivery: bool = False) -> OrderQuoteOut:
        delivery_fee = (
            0
            if free_delivery or subtotal_cents >= settings.delivery_free_threshold
            else settings.delivery_base_fee
        )
        amount_to_free_delivery = max(
            0,
            settings.delivery_free_threshold - subtotal_cents,
        )
        if free_delivery:
            amount_to_free_delivery = 0

        return OrderQuoteOut(
            subtotal_cents=subtotal_cents,
            delivery_fee_cents=delivery_fee,
            free_delivery_threshold_cents=settings.delivery_free_threshold,
            amount_to_free_delivery_cents=amount_to_free_delivery,
        )

    async def create_order(self, profile_id: str, payload: OrderCreate) -> OrderOut:
        address_resp = (
            self.db.table("addresses")
            .select("*")
            .eq("id", str(payload.address_id))
            .eq("profile_id", profile_id)
            .single()
            .execute()
        )
        if not address_resp.data:
            raise NotFoundError("Endereco")

        # 1. Buscar produtos e calcular subtotal
        product_ids = [str(item.product_id) for item in payload.items]
        products_resp = (
            self.write_db.table("products")
            .select("id, name, price, available")
            .in_("id", product_ids)
            .execute()
        )
        products = {p["id"]: p for p in products_resp.data}

        if len(products) != len(product_ids):
            raise NotFoundError("Um ou mais produtos")

        unavailable = [p["name"] for p in products.values() if not p["available"]]
        if unavailable:
            raise UnprocessableError(
                f"Produto(s) indisponível(is): {', '.join(unavailable)}"
            )

        subtotal_cents = sum(
            int(Decimal(str(products[str(item.product_id)]["price"])) * 100)
            * item.quantity
            for item in payload.items
        )

        # 2. Calcular frete
        delivery_fee = self.quote(subtotal_cents=subtotal_cents).delivery_fee_cents

        # 3. Aplicar promoção (se houver)
        discount = 0
        promotion_id = None
        if payload.promotion_code:
            result = await self.promotion.validate(
                code=payload.promotion_code,
                profile_id=profile_id,
                order_subtotal=subtotal_cents,
            )
            if not result.valid:
                raise UnprocessableError(result.description or "Cupom invalido")
            discount = result.discount
            promotion_id = result.promotion_id
            if result.type and result.type.value == "free_delivery":
                delivery_fee = 0

        total = subtotal_cents + delivery_fee - discount

        # 4. Persistir pedido
        order_data = {
            "profile_id": profile_id,
            "address_id": str(payload.address_id),
            "payment_method": payload.payment_method.value,
            "payment_status": "pending",
            "status": OrderStatus.PENDING.value,
            "subtotal": subtotal_cents / 100,
            "delivery_fee": delivery_fee / 100,
            "discount": discount / 100,
            "total": total / 100,
            "notes": payload.notes,
        }
        order_resp = self.write_db.table("orders").insert(order_data).execute()
        order = order_resp.data[0]
        order_id = order["id"]
        customer = self._get_customer(profile_id)
        try:
            payment = self.payments.prepare(
                order=order,
                payment_method=payload.payment_method.value,
                customer=customer,
            )
            payment_status = str(payment.payload.get("status") or "pending")
            payment_update = {
                "payment_provider": payment.provider.value,
                "payment_reference": payment.reference,
                "payment_status": payment_status,
                "payment_payload": payment.payload,
            }
            if payment_status == "paid":
                payment_update["paid_at"] = datetime.now(UTC).isoformat()
        except PaymentProviderError:
            logger.exception("Payment creation failed order_id=%s", order_id)
            payment_update = {
                "payment_provider": "mercado_pago",
                "payment_reference": None,
                "payment_status": "failed",
                "payment_payload": {
                    "title": "Pix indisponivel",
                    "description": (
                        "Nao foi possivel gerar o Pix agora. Tente fazer um novo "
                        "pedido ou fale com a equipe Lugano."
                    ),
                    "method": "pix",
                    "status": "failed",
                },
            }
        (
            self.write_db.table("orders")
            .update(payment_update)
            .eq("id", order_id)
            .execute()
        )
        order.update(payment_update)

        # 5. Persistir itens
        items_data = [
            {
                "order_id": order_id,
                "product_id": str(item.product_id),
                "quantity": item.quantity,
                "unit_price": products[str(item.product_id)]["price"],
                "customization": item.customization,
            }
            for item in payload.items
        ]
        self.write_db.table("order_items").insert(items_data).execute()

        # 6. Registrar uso da promoção
        if promotion_id:
            await self.promotion.register_usage(
                promotion_id=promotion_id,
                profile_id=profile_id,
                order_id=order_id,
                discount_applied=discount / 100,
            )

        # Fidelidade e entrega sao efeitos posteriores ao pagamento. Eles sao
        # executados pelas transicoes do ciclo do pedido, nunca na criacao.
        await self.notifications.safe_notify_order_status(order)

        if order.get("payment_status") == "paid":
            await OrderLifecycleService(self.write_db).payment_approved(order_id)

        return await self.get_order(order_id=order_id, profile_id=profile_id)

    async def get_order(self, order_id: str, profile_id: str) -> OrderOut:
        resp = (
            self.db.table("orders")
            .select("*, order_items(*)")
            .eq("id", order_id)
            .eq("profile_id", profile_id)
            .single()
            .execute()
        )
        if not resp.data:
            raise NotFoundError("Pedido", order_id)
        return self._to_order_out(resp.data)

    async def list_orders(
        self,
        profile_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> list[OrderOut]:
        offset = (page - 1) * page_size
        resp = (
            self.db.table("orders")
            .select("*, order_items(*)")
            .eq("profile_id", profile_id)
            .order("placed_at", desc=True)
            .range(offset, offset + page_size - 1)
            .execute()
        )
        return [self._to_order_out(o) for o in resp.data]

    async def cancel_order(self, order_id: str, profile_id: str) -> OrderOut:
        order = await self.get_order(order_id=order_id, profile_id=profile_id)

        cancellable = {OrderStatus.PENDING, OrderStatus.CONFIRMED}
        if order.status not in cancellable:
            raise UnprocessableError(
                f"Pedido com status '{order.status}' não pode ser cancelado"
            )

        (
            self.write_db.table("orders")
            .update({"status": OrderStatus.CANCELLED.value})
            .eq("id", order_id)
            .eq("profile_id", profile_id)
            .execute()
        )

        # Estornar pontos creditados
        await self.loyalty.reverse_points(order_id=order_id, profile_id=profile_id)

        return await self.get_order(order_id=order_id, profile_id=profile_id)
