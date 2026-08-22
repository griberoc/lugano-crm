import hashlib
import hmac

from app.db.client import get_supabase_admin
from app.main import app
from app.services.payment import (
    PaymentNotFoundError,
    PaymentProviderError,
    PaymentService,
)


def webhook_headers(secret: str, payment_id: str) -> dict[str, str]:
    request_id = "request-payment-test"
    timestamp = "1704908010"
    manifest = f"id:{payment_id};request-id:{request_id};ts:{timestamp};"
    signature = hmac.new(
        secret.encode(),
        manifest.encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "X-Request-ID": request_id,
        "X-Signature": f"ts={timestamp},v1={signature}",
    }


def seed_order(fake_db):
    fake_db.tables["orders"].append(
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "profile_id": "22222222-2222-2222-2222-222222222222",
            "payment_provider": "mercado_pago",
            "payment_reference": "123456789",
            "payment_status": "pending",
            "payment_payload": {"status": "pending"},
            "status": "pending",
            "total": "24.90",
            "order_items": [],
        }
    )


def test_webhook_approves_order_and_audits_event(client, fake_db, monkeypatch):
    from app.core.config import settings

    seed_order(fake_db)
    monkeypatch.setattr(settings, "mercado_pago_webhook_secret", "test-secret")
    monkeypatch.setattr(
        PaymentService,
        "get_mercado_pago_payment",
        lambda _self, _payment_id: {
            "id": 123456789,
            "external_reference": "11111111-1111-1111-1111-111111111111",
            "status": "approved",
            "status_detail": "accredited",
            "transaction_amount": 24.90,
            "currency_id": "BRL",
            "date_approved": "2026-08-22T10:00:00Z",
        },
    )
    app.dependency_overrides[get_supabase_admin] = lambda: fake_db

    response = client.post(
        "/api/v1/payments/mercado-pago/webhook?data.id=123456789",
        headers=webhook_headers("test-secret", "123456789"),
        json={"type": "payment", "data": {"id": "123456789"}},
    )

    assert response.status_code == 200
    assert response.json()["payment_status"] == "paid"
    assert fake_db.tables["orders"][0]["payment_status"] == "paid"
    assert fake_db.tables["orders"][0]["status"] == "confirmed"
    assert fake_db.tables["audit_logs"][0]["action"] == "payment.webhook"


def test_webhook_rejects_invalid_signature(client, fake_db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "mercado_pago_webhook_secret", "test-secret")
    app.dependency_overrides[get_supabase_admin] = lambda: fake_db

    response = client.post(
        "/api/v1/payments/mercado-pago/webhook?data.id=123456789",
        headers={"X-Request-ID": "request", "X-Signature": "ts=1,v1=invalid"},
        json={"data": {"id": "123456789"}},
    )

    assert response.status_code == 401
    assert fake_db.tables["orders"] == []


def test_webhook_returns_safe_message_when_provider_fails(client, fake_db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "mercado_pago_webhook_secret", "")
    monkeypatch.setattr(
        PaymentService,
        "get_mercado_pago_payment",
        lambda _self, _payment_id: (_ for _ in ()).throw(
            PaymentProviderError("provider detail must not leak")
        ),
    )
    app.dependency_overrides[get_supabase_admin] = lambda: fake_db

    response = client.post(
        "/api/v1/payments/mercado-pago/webhook",
        json={"data": {"id": "123456789"}},
    )

    assert response.status_code == 502
    assert "provider detail" not in response.text
    assert "Tente novamente" in response.json()["detail"]


def test_webhook_acknowledges_unknown_simulator_payment(client, fake_db, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "mercado_pago_webhook_secret", "")
    monkeypatch.setattr(
        PaymentService,
        "get_mercado_pago_payment",
        lambda _self, _payment_id: (_ for _ in ()).throw(
            PaymentNotFoundError("Payment not found")
        ),
    )
    app.dependency_overrides[get_supabase_admin] = lambda: fake_db

    response = client.post(
        "/api/v1/payments/mercado-pago/webhook",
        json={"type": "payment", "data": {"id": "1234567"}},
    )

    assert response.status_code == 200
    assert response.json() == {
        "received": True,
        "ignored": True,
        "reason": "payment_not_found",
        "payment_id": "1234567",
    }
