import hashlib
import hmac
from decimal import Decimal

from app.core.config import settings
from app.services.payment import (
    PaymentProvider,
    PaymentService,
    build_pix_copy_paste,
    crc16_ccitt,
    normalize_txid,
    verify_mercado_pago_signature,
)


def test_crc16_ccitt_matches_known_pix_sample_suffix():
    assert crc16_ccitt("123456789") == "29B1"


def test_build_pix_copy_paste_contains_amount_key_and_crc():
    code = build_pix_copy_paste(
        pix_key="financeiro@lugano.com.br",
        merchant_name="Lugano Café",
        merchant_city="Gramado",
        amount=Decimal("24.90"),
        txid="LUG123",
        description="Pedido Lugano",
    )

    assert "br.gov.bcb.pix" in code
    assert "financeiro@lugano.com.br" in code
    assert "540524.90" in code
    assert code[-8:-4] == "6304"
    assert code[-4:] == crc16_ccitt(code[:-4])


def test_normalize_txid_keeps_pix_limit():
    assert normalize_txid("lug-123456789012345678901234567890") == (
        "LUG1234567890123456789012"
    )


def test_payment_service_prepares_pix_static(monkeypatch):
    monkeypatch.setattr(settings, "payment_provider", "pix_static")
    monkeypatch.setattr(settings, "pix_key", "financeiro@lugano.com.br")
    monkeypatch.setattr(settings, "pix_merchant_name", "Lugano")
    monkeypatch.setattr(settings, "pix_merchant_city", "Gramado")
    monkeypatch.setattr(settings, "pix_txid_prefix", "LUG")

    payment = PaymentService().prepare(
        order={"id": "11111111-1111-1111-1111-111111111111", "total": "24.90"},
        payment_method="pix",
    )

    assert payment.provider == PaymentProvider.PIX_STATIC
    assert payment.payload["pix_copy_paste"]
    assert payment.payload["pix_key"] == "financeiro@lugano.com.br"
    assert payment.payload["status"] == "pending"


def test_payment_service_falls_back_to_manual_pix_without_key(monkeypatch):
    monkeypatch.setattr(settings, "payment_provider", "pix_static")
    monkeypatch.setattr(settings, "pix_key", None)

    payment = PaymentService().prepare(
        order={"id": "11111111-1111-1111-1111-111111111111", "total": "24.90"},
        payment_method="pix",
    )

    assert payment.provider == PaymentProvider.MANUAL
    assert payment.payload["title"] == "Pix manual"


def test_payment_service_prepares_mercado_pago_pix(monkeypatch):
    monkeypatch.setattr(settings, "payment_provider", "mercado_pago")
    monkeypatch.setattr(settings, "mercado_pago_access_token", "TEST-123")
    monkeypatch.setattr(
        settings,
        "mercado_pago_notification_url",
        "https://api.lugano.test/api/v1/payments/mercado-pago/webhook",
    )

    def fake_request(self, method, path, *, json=None, idempotency_key=None):
        assert method == "POST"
        assert path == "/v1/payments"
        assert json["payment_method_id"] == "pix"
        assert json["payer"]["email"] == "cliente@lugano.test"
        assert json["external_reference"] == "11111111-1111-1111-1111-111111111111"
        assert idempotency_key == "lugano-order-11111111-1111-1111-1111-111111111111"
        return {
            "id": 123456789,
            "status": "pending",
            "status_detail": "pending_waiting_transfer",
            "point_of_interaction": {
                "transaction_data": {
                    "qr_code": "000201-MP",
                    "qr_code_base64": "iVBORw0KGgo=",
                    "ticket_url": "https://www.mercadopago.com.br/payments/123/ticket",
                }
            },
        }

    monkeypatch.setattr(PaymentService, "_request_mercado_pago", fake_request)

    payment = PaymentService().prepare(
        order={"id": "11111111-1111-1111-1111-111111111111", "total": "24.90"},
        payment_method="pix",
        customer={"email": "cliente@lugano.test"},
    )

    assert payment.provider == PaymentProvider.MERCADO_PAGO
    assert payment.reference == "123456789"
    assert payment.payload["pix_copy_paste"] == "000201-MP"
    assert payment.payload["pix_qr_code_base64"] == "iVBORw0KGgo="
    assert payment.payload["payment_url"].startswith("https://www.mercadopago")


def test_verify_mercado_pago_signature_accepts_valid_hmac():
    secret = "webhook-secret"
    data_id = "123456789"
    request_id = "request-1"
    timestamp = "1704908010"
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    signature = hmac.new(
        secret.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    assert verify_mercado_pago_signature(
        x_signature=f"ts={timestamp},v1={signature}",
        x_request_id=request_id,
        data_id=data_id,
        secret=secret,
    )


def test_verify_mercado_pago_signature_rejects_invalid_hmac():
    assert not verify_mercado_pago_signature(
        x_signature="ts=1704908010,v1=wrong",
        x_request_id="request-1",
        data_id="123456789",
        secret="webhook-secret",
    )


def test_sync_mercado_pago_payment_updates_order(fake_db, monkeypatch):
    fake_db.tables["orders"].append(
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "payment_provider": "mercado_pago",
            "payment_reference": "123456789",
            "payment_status": "pending",
            "payment_payload": {
                "title": "Pix Mercado Pago",
                "description": "Pague via Pix",
                "method": "pix",
                "status": "pending",
            },
        }
    )

    def fake_get_payment(self, payment_id):
        assert payment_id == "123456789"
        return {
            "id": 123456789,
            "external_reference": "11111111-1111-1111-1111-111111111111",
            "status": "approved",
            "status_detail": "accredited",
            "date_approved": "2026-08-19T10:00:00Z",
        }

    monkeypatch.setattr(PaymentService, "get_mercado_pago_payment", fake_get_payment)

    result = PaymentService().sync_mercado_pago_payment(
        db=fake_db,
        payment_id="123456789",
    )

    assert result["updated"] is True
    assert fake_db.tables["orders"][0]["payment_status"] == "paid"
    assert fake_db.tables["orders"][0]["paid_at"] == "2026-08-19T10:00:00Z"
    assert fake_db.tables["orders"][0]["payment_payload"]["status"] == "paid"
