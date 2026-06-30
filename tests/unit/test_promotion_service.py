from unittest.mock import MagicMock

import pytest

from app.core.exceptions import PromotionExpiredError, PromotionLimitReachedError
from app.services.promotion import PromotionService


def make_promo(**overrides) -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "code": "CAFE10",
        "type": "percentage",
        "value": 10,
        "min_order_cents": 2000,
        "max_uses": 100,
        "uses_count": 5,
        "active": True,
        "starts_at": None,
        "expires_at": None,
        **overrides,
    }


def promotion_result(db):
    return (
        db.table.return_value.select.return_value.eq.return_value.eq.return_value
        .single.return_value.execute.return_value
    )


def usage_result(db):
    return (
        db.table.return_value.select.return_value.eq.return_value.eq.return_value
        .execute.return_value
    )


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def service(db):
    return PromotionService(db)


@pytest.mark.asyncio
async def test_validate_valid_coupon(service, db):
    promotion_result(db).data = make_promo()
    usage_result(db).data = []

    result = await service.validate(
        code="CAFE10",
        profile_id="user-1",
        order_subtotal=5000,
    )

    assert result.valid is True
    assert result.discount == 500


@pytest.mark.asyncio
async def test_validate_expired_coupon(service, db):
    promotion_result(db).data = make_promo(
        expires_at="2020-01-01T00:00:00+00:00",
    )

    with pytest.raises(PromotionExpiredError):
        await service.validate(
            code="CAFE10",
            profile_id="user-1",
            order_subtotal=5000,
        )


@pytest.mark.asyncio
async def test_validate_limit_reached(service, db):
    promotion_result(db).data = make_promo(max_uses=10, uses_count=10)

    with pytest.raises(PromotionLimitReachedError):
        await service.validate(
            code="CAFE10",
            profile_id="user-1",
            order_subtotal=5000,
        )


@pytest.mark.asyncio
async def test_validate_below_minimum_order(service, db):
    promotion_result(db).data = make_promo(min_order_cents=5000)
    usage_result(db).data = []

    result = await service.validate(
        code="CAFE10",
        profile_id="user-1",
        order_subtotal=1000,
    )

    assert result.valid is False
    assert "minimo" in result.description


@pytest.mark.asyncio
async def test_list_available_promotions_filters_unusable(service, db):
    query = db.table.return_value.select.return_value.eq.return_value
    query.order.return_value.execute.return_value.data = [
        make_promo(description="Campanha valida"),
        make_promo(
            id="22222222-2222-2222-2222-222222222222",
            code="EXPIRADO",
            expires_at="2020-01-01T00:00:00+00:00",
        ),
        make_promo(
            id="33333333-3333-3333-3333-333333333333",
            code="ESGOTADO",
            max_uses=10,
            uses_count=10,
        ),
    ]

    result = await service.list_available(tier_name="Ouro")

    assert len(result) == 1
    assert result[0].code == "CAFE10"
    assert result[0].audience == "Disponivel para seu nivel Ouro"
