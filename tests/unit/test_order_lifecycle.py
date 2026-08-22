import pytest

from app.services.order_lifecycle import OrderLifecycleService


def seed_paid_order(fake_db, *, payment_status="paid", status="pending"):
    profile_id = "11111111-1111-1111-1111-111111111111"
    order_id = "22222222-2222-2222-2222-222222222222"
    account_id = "33333333-3333-3333-3333-333333333333"
    tier_id = "44444444-4444-4444-4444-444444444444"
    fake_db.tables["orders"].append(
        {
            "id": order_id,
            "profile_id": profile_id,
            "address_id": "55555555-5555-5555-5555-555555555555",
            "status": status,
            "payment_status": payment_status,
            "total": "24.90",
            "order_items": [],
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
        {"id": tier_id, "name": "Bronze", "min_points": 0}
    )
    return order_id


@pytest.mark.asyncio
async def test_payment_approved_confirms_order_and_credits_points_once(fake_db):
    order_id = seed_paid_order(fake_db)
    lifecycle = OrderLifecycleService(fake_db)

    await lifecycle.payment_approved(order_id)
    await lifecycle.payment_approved(order_id)

    assert fake_db.tables["orders"][0]["status"] == "confirmed"
    assert fake_db.tables["loyalty_accounts"][0]["available_points"] == 240
    assert len(fake_db.tables["loyalty_transactions"]) == 1


@pytest.mark.asyncio
async def test_pending_payment_has_no_lifecycle_effects(fake_db):
    order_id = seed_paid_order(fake_db, payment_status="pending")

    await OrderLifecycleService(fake_db).payment_approved(order_id)

    assert fake_db.tables["orders"][0]["status"] == "pending"
    assert fake_db.tables["loyalty_accounts"][0]["available_points"] == 0
    assert fake_db.tables["loyalty_transactions"] == []
