from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.core.config import settings
from app.core.exceptions import NotFoundError, UnprocessableError
from app.schemas.loyalty import PromotionValidateResponse
from app.schemas.order import OrderCreate, OrderItemCreate, PaymentMethod
from app.services.order import OrderService


def make_order(**overrides):
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "status": "pending",
        "payment_method": "pix",
        "payment_status": "pending",
        "subtotal": "19.90",
        "delivery_fee": "5.00",
        "discount": "0.00",
        "total": "24.90",
        "notes": None,
        "placed_at": datetime.now(UTC).isoformat(),
        "delivered_at": None,
        "order_items": [
            {
                "id": "22222222-2222-2222-2222-222222222222",
                "product_id": "33333333-3333-3333-3333-333333333333",
                "quantity": 1,
                "unit_price": "19.90",
                "customization": "sem canela",
            }
        ],
        **overrides,
    }


def test_to_order_out_maps_supabase_order_items_to_items():
    service = OrderService(db=None)

    order = service._to_order_out(make_order())

    assert len(order.items) == 1
    assert order.items[0].customization == "sem canela"


def test_to_order_out_maps_payment_payload_to_instructions():
    service = OrderService(db=None)

    order = service._to_order_out(
        make_order(
            payment_provider="pix_static",
            payment_payload={
                "title": "Pix copia e cola",
                "description": "Use o codigo Pix",
                "method": "pix",
                "status": "pending",
                "pix_copy_paste": "000201...",
            },
        )
    )

    assert order.payment_provider == "pix_static"
    assert order.payment_instructions.pix_copy_paste == "000201..."


def test_to_order_out_preserves_existing_items_key():
    service = OrderService(db=None)
    data = make_order(items=make_order()["order_items"])
    data.pop("order_items")

    order = service._to_order_out(data)

    assert len(order.items) == 1


def test_quote_applies_base_delivery_fee():
    service = OrderService(db=None)

    quote = service.quote(subtotal_cents=1990)

    assert quote.delivery_fee_cents == 500
    assert quote.amount_to_free_delivery_cents == 3010


def test_quote_applies_free_delivery_threshold():
    service = OrderService(db=None)

    quote = service.quote(subtotal_cents=5000)

    assert quote.delivery_fee_cents == 0
    assert quote.amount_to_free_delivery_cents == 0


def test_quote_applies_free_delivery_coupon():
    service = OrderService(db=None)

    quote = service.quote(subtotal_cents=1990, free_delivery=True)

    assert quote.delivery_fee_cents == 0
    assert quote.amount_to_free_delivery_cents == 0


class InvalidPromotionService:
    async def validate(self, **_kwargs):
        return PromotionValidateResponse(valid=False, description="Cupom invalido")


@pytest.mark.asyncio
async def test_create_order_rejects_invalid_coupon(fake_db):
    profile_id = "11111111-1111-1111-1111-111111111111"
    address_id = "22222222-2222-2222-2222-222222222222"
    product_id = "33333333-3333-3333-3333-333333333333"
    fake_db.tables["addresses"].append(
        {
            "id": address_id,
            "profile_id": profile_id,
        }
    )
    fake_db.tables["products"].append(
        {
            "id": product_id,
            "name": "Chocolate Quente Lugano",
            "price": "19.90",
            "available": True,
        }
    )
    service = OrderService(db=fake_db, write_db=fake_db)
    service.promotion = InvalidPromotionService()

    with pytest.raises(UnprocessableError):
        await service.create_order(
            profile_id=profile_id,
            payload=OrderCreate(
                address_id=address_id,
                payment_method=PaymentMethod.PIX,
                promotion_code="INVALIDO",
                items=[OrderItemCreate(product_id=product_id, quantity=1)],
            ),
        )


@pytest.mark.asyncio
async def test_create_order_rejects_address_from_another_customer(fake_db):
    service = OrderService(db=fake_db, write_db=fake_db)

    with pytest.raises(NotFoundError):
        await service.create_order(
            profile_id="11111111-1111-1111-1111-111111111111",
            payload=OrderCreate(
                address_id="22222222-2222-2222-2222-222222222222",
                payment_method=PaymentMethod.PIX,
                items=[
                    OrderItemCreate(
                        product_id="33333333-3333-3333-3333-333333333333",
                        quantity=1,
                    )
                ],
            ),
        )


@pytest.mark.asyncio
async def test_create_order_persists_order_items_and_loyalty_points(fake_db):
    previous_email_webhook = settings.notification_email_webhook_url
    previous_whatsapp_webhook = settings.notification_whatsapp_webhook_url
    previous_enabled = settings.notifications_enabled
    previous_email_enabled = settings.notification_email_enabled
    previous_whatsapp_enabled = settings.notification_whatsapp_enabled
    previous_payment_provider = settings.payment_provider
    previous_pix_key = settings.pix_key
    settings.notifications_enabled = True
    settings.notification_email_enabled = True
    settings.notification_whatsapp_enabled = True
    settings.notification_email_webhook_url = None
    settings.notification_whatsapp_webhook_url = None
    settings.payment_provider = "pix_static"
    settings.pix_key = "financeiro@lugano.com.br"
    profile_id = "11111111-1111-1111-1111-111111111111"
    address_id = "22222222-2222-2222-2222-222222222222"
    product_id = "33333333-3333-3333-3333-333333333333"
    tier_id = "44444444-4444-4444-4444-444444444444"
    account_id = "55555555-5555-5555-5555-555555555555"
    fake_db.defaults["orders"] = {
        "placed_at": fake_db.now,
        "delivered_at": None,
    }
    fake_db.tables["profiles"].append(
        {
            "id": profile_id,
            "full_name": "Cliente Lugano",
            "email": "cliente@lugano.test",
            "phone": "11999999999",
            "preferences": {"accepts_whatsapp": True},
        }
    )
    fake_db.tables["addresses"].append(
        {
            "id": address_id,
            "profile_id": profile_id,
        }
    )
    fake_db.tables["products"].append(
        {
            "id": product_id,
            "name": "Chocolate Quente Lugano",
            "price": "19.90",
            "available": True,
        }
    )
    fake_db.tables["loyalty_accounts"].append(
        {
            "id": account_id,
            "profile_id": profile_id,
            "tier_id": tier_id,
            "total_points": 0,
            "available_points": 0,
        }
    )
    fake_db.tables["loyalty_tiers"].append(
        {
            "id": tier_id,
            "name": "Bronze",
            "min_points": 0,
            "cashback_rate": "0",
            "benefits": {},
        }
    )

    try:
        service = OrderService(db=fake_db, write_db=fake_db)
        order = await service.create_order(
            profile_id=profile_id,
            payload=OrderCreate(
                address_id=address_id,
                payment_method=PaymentMethod.PIX,
                items=[OrderItemCreate(product_id=product_id, quantity=1)],
            ),
        )
    finally:
        settings.notification_email_webhook_url = previous_email_webhook
        settings.notification_whatsapp_webhook_url = previous_whatsapp_webhook
        settings.notifications_enabled = previous_enabled
        settings.notification_email_enabled = previous_email_enabled
        settings.notification_whatsapp_enabled = previous_whatsapp_enabled
        settings.payment_provider = previous_payment_provider
        settings.pix_key = previous_pix_key

    assert order.total == Decimal("24.9")
    assert order.payment_provider == "pix_static"
    assert order.payment_instructions.pix_copy_paste
    assert fake_db.tables["order_items"][0]["product_id"] == product_id
    assert fake_db.tables["orders"][0]["payment_provider"] == "pix_static"
    assert fake_db.tables["loyalty_accounts"][0]["available_points"] == 240
    assert fake_db.tables["loyalty_transactions"][0]["points"] == 240
    assert fake_db.tables["notification_events"][0]["event_type"] == "order_created"
