from decimal import Decimal

from app.core.config import settings
from app.services.payment import (
    PaymentProvider,
    PaymentService,
    build_pix_copy_paste,
    crc16_ccitt,
    normalize_txid,
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
