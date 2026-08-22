import pytest
import httpx

from app.core.config import settings
from app.services.delivery import (
    DeliveryProviderError,
    DeliveryService,
    MachineDeliveryProvider,
    money_to_cents,
)


DELIVERY_SETTING_KEYS = (
    "delivery_api_base_url",
    "delivery_api_key",
    "delivery_api_username",
    "delivery_api_password",
    "delivery_origin_address",
    "delivery_origin_neighborhood",
    "delivery_origin_city",
    "delivery_origin_state",
    "delivery_origin_complement",
    "delivery_origin_reference",
    "delivery_origin_lat",
    "delivery_origin_lng",
    "delivery_default_destination_state",
    "delivery_machine_category_id",
    "delivery_machine_category_name",
    "delivery_machine_payment_method",
)


def snapshot_delivery_settings():
    return {key: getattr(settings, key) for key in DELIVERY_SETTING_KEYS}


def restore_delivery_settings(previous):
    for key, value in previous.items():
        setattr(settings, key, value)


def configure_machine_settings():
    settings.delivery_api_base_url = (
        "https://api-vendas.taximachine.com.br/api/v2/integracao"
    )
    settings.delivery_api_key = "machine-api-key"
    settings.delivery_api_username = "lugano"
    settings.delivery_api_password = "secret"
    settings.delivery_origin_address = "Avenida Colares Moreira, 10"
    settings.delivery_origin_neighborhood = "Jardim Renascenca"
    settings.delivery_origin_city = "Sao Luis"
    settings.delivery_origin_state = "MA"
    settings.delivery_origin_complement = "Loja 1"
    settings.delivery_origin_reference = "Lugano Sao Luis"
    settings.delivery_origin_lat = -2.505
    settings.delivery_origin_lng = -44.299
    settings.delivery_default_destination_state = "MA"
    settings.delivery_machine_category_id = 123
    settings.delivery_machine_category_name = "Moto"
    settings.delivery_machine_payment_method = "F"


@pytest.mark.asyncio
async def test_manual_delivery_quote_uses_existing_fee_rules():
    previous_base_fee = settings.delivery_base_fee
    previous_threshold = settings.delivery_free_threshold
    previous_provider = settings.delivery_provider
    settings.delivery_base_fee = 700
    settings.delivery_free_threshold = 5000
    settings.delivery_provider = "manual"

    try:
        quote = await DeliveryService().quote(subtotal_cents=1990)
        free_quote = await DeliveryService().quote(subtotal_cents=5000)
    finally:
        settings.delivery_base_fee = previous_base_fee
        settings.delivery_free_threshold = previous_threshold
        settings.delivery_provider = previous_provider

    assert quote.provider == "manual"
    assert quote.delivery_fee_cents == 700
    assert free_quote.delivery_fee_cents == 0


@pytest.mark.asyncio
async def test_safe_dispatch_respects_feature_flag(fake_db):
    previous_auto_dispatch = settings.delivery_auto_dispatch_enabled
    settings.delivery_auto_dispatch_enabled = False

    try:
        dispatch = await DeliveryService(fake_db).safe_dispatch_order(
            order={"id": "11111111-1111-1111-1111-111111111111"},
            customer=None,
            address=None,
            items=[],
        )
    finally:
        settings.delivery_auto_dispatch_enabled = previous_auto_dispatch

    assert dispatch is None
    assert fake_db.tables["delivery_dispatches"] == []


@pytest.mark.asyncio
async def test_manual_dispatch_records_delivery_dispatch(fake_db):
    previous_auto_dispatch = settings.delivery_auto_dispatch_enabled
    previous_provider = settings.delivery_provider
    settings.delivery_auto_dispatch_enabled = True
    settings.delivery_provider = "manual"

    try:
        dispatch = await DeliveryService(fake_db).safe_dispatch_order(
            order={
                "id": "11111111-1111-1111-1111-111111111111",
                "payment_status": "paid",
            },
            customer={"id": "22222222-2222-2222-2222-222222222222"},
            address={"id": "33333333-3333-3333-3333-333333333333"},
            items=[{"quantity": 1}],
        )
    finally:
        settings.delivery_auto_dispatch_enabled = previous_auto_dispatch
        settings.delivery_provider = previous_provider

    assert dispatch.status == "manual_pending"
    assert fake_db.tables["delivery_dispatches"][0]["provider"] == "manual"
    assert fake_db.tables["delivery_dispatches"][0]["status"] == "manual_pending"


@pytest.mark.asyncio
async def test_dispatch_blocks_unpaid_order_and_does_not_duplicate(fake_db):
    previous_auto_dispatch = settings.delivery_auto_dispatch_enabled
    previous_provider = settings.delivery_provider
    settings.delivery_auto_dispatch_enabled = True
    settings.delivery_provider = "manual"
    service = DeliveryService(fake_db)

    try:
        unpaid = await service.safe_dispatch_order(
            order={"id": "order-1", "payment_status": "pending"},
            customer=None,
            address=None,
            items=[],
        )
        first = await service.safe_dispatch_order(
            order={"id": "order-1", "payment_status": "paid"},
            customer=None,
            address=None,
            items=[],
        )
        repeated = await service.safe_dispatch_order(
            order={"id": "order-1", "payment_status": "paid"},
            customer=None,
            address=None,
            items=[],
        )
    finally:
        settings.delivery_auto_dispatch_enabled = previous_auto_dispatch
        settings.delivery_provider = previous_provider

    assert unpaid is None
    assert first is not None
    assert repeated is None
    assert len(fake_db.tables["delivery_dispatches"]) == 1


def test_machine_headers_use_basic_auth_and_api_key():
    previous = snapshot_delivery_settings()
    configure_machine_settings()

    try:
        headers = MachineDeliveryProvider()._headers()
    finally:
        restore_delivery_settings(previous)

    assert headers["api-key"] == "machine-api-key"
    assert headers["Authorization"] == "Basic bHVnYW5vOnNlY3JldA=="
    assert headers["Content-Type"] == "application/json"


def test_machine_quote_payload_maps_lugano_address():
    previous = snapshot_delivery_settings()
    configure_machine_settings()

    try:
        payload = MachineDeliveryProvider()._quote_payload(
            {
                "street": "Rua das Flores",
                "number": "25",
                "neighborhood": "Ponta do Farol",
                "city": "Sao Luis",
            }
        )
    finally:
        restore_delivery_settings(previous)

    assert payload["endereco_partida"] == "Avenida Colares Moreira, 10"
    assert payload["bairro_partida"] == "Jardim Renascenca"
    assert payload["endereco_desejado"] == "Rua das Flores, 25"
    assert payload["bairro_desejado"] == "Ponta do Farol"
    assert payload["estado_desejado"] == "MA"
    assert payload["categoria_id"] == 123


def test_machine_dispatch_payload_maps_order_customer_and_destination():
    previous = snapshot_delivery_settings()
    configure_machine_settings()

    try:
        payload = MachineDeliveryProvider()._dispatch_payload(
            order={
                "id": "11111111-1111-1111-1111-111111111111",
                "total": "42.90",
                "notes": "Tocar interfone",
            },
            customer={
                "full_name": "Cliente Lugano",
                "phone": "98999999999",
            },
            address={
                "street": "Rua das Flores",
                "number": "25",
                "complement": "Apto 401",
                "neighborhood": "Ponta do Farol",
                "city": "Sao Luis",
            },
        )
    finally:
        restore_delivery_settings(previous)

    parada = payload["paradas"][0]
    assert payload["forma_pagamento"] == "F"
    assert payload["partida"]["referencia"] == "Lugano Sao Luis"
    assert parada["id_externo"] == "11111111-1111-1111-1111-111111111111"
    assert parada["nome_cliente_parada"] == "Cliente Lugano"
    assert parada["telefone_cliente_parada"] == "98999999999"
    assert parada["valor_cobrar"] == 42.9


def test_money_to_cents_uses_decimal_rounding():
    assert money_to_cents("846.18") == 84618
    assert money_to_cents("10.999") == 1100


def test_machine_decode_response_includes_error_body():
    response = httpx.Response(
        403,
        json={"message": "API key sem permissao para integracao"},
        request=httpx.Request(
            "POST",
            "https://api-vendas.taximachine.com.br/api/v2/integracao/entregas/estimativas",
        ),
    )

    with pytest.raises(DeliveryProviderError, match="403 Forbidden.*API key"):
        MachineDeliveryProvider()._decode_response(response)
