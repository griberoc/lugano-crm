from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.core.config import settings


class PaymentProvider(StrEnum):
    MANUAL = "manual"
    PIX_STATIC = "pix_static"
    MERCADO_PAGO = "mercado_pago"


@dataclass(frozen=True)
class PaymentPreparation:
    provider: PaymentProvider
    reference: str | None
    payload: dict[str, Any]


def emv_field(field_id: str, value: str) -> str:
    return f"{field_id}{len(value):02d}{value}"


def normalize_emv_text(value: str, max_length: int) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^A-Za-z0-9 .,&-]", "", ascii_text)
    ascii_text = re.sub(r"\s+", " ", ascii_text).strip().upper()
    return ascii_text[:max_length] or "LUGANO"


def normalize_txid(value: str) -> str:
    txid = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return txid[:25] or "***"


def crc16_ccitt(payload: str) -> str:
    crc = 0xFFFF
    for byte in payload.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def build_pix_copy_paste(
    *,
    pix_key: str,
    merchant_name: str,
    merchant_city: str,
    amount: Decimal,
    txid: str,
    description: str | None = None,
) -> str:
    merchant_account_fields = [
        emv_field("00", "br.gov.bcb.pix"),
        emv_field("01", pix_key.strip()),
    ]
    if description:
        merchant_account_fields.append(
            emv_field("02", normalize_emv_text(description, 72)),
        )

    additional_data = emv_field("05", normalize_txid(txid))
    amount_text = f"{amount:.2f}"
    payload_without_crc = "".join(
        [
            emv_field("00", "01"),
            emv_field("26", "".join(merchant_account_fields)),
            emv_field("52", "0000"),
            emv_field("53", "986"),
            emv_field("54", amount_text),
            emv_field("58", "BR"),
            emv_field("59", normalize_emv_text(merchant_name, 25)),
            emv_field("60", normalize_emv_text(merchant_city, 15)),
            emv_field("62", additional_data),
            "6304",
        ],
    )
    return f"{payload_without_crc}{crc16_ccitt(payload_without_crc)}"


class PaymentService:
    def prepare(self, order: dict[str, Any], payment_method: str) -> PaymentPreparation:
        if payment_method == "pix" and settings.payment_provider == "pix_static":
            return self._prepare_pix_static(order)

        if payment_method == "pix":
            return self._prepare_manual_pix(order)

        return self._prepare_manual_delivery(order, payment_method)

    def _prepare_manual_pix(self, order: dict[str, Any]) -> PaymentPreparation:
        return PaymentPreparation(
            provider=PaymentProvider.MANUAL,
            reference=str(order.get("id") or ""),
            payload={
                "title": "Pix manual",
                "description": (
                    "A equipe Lugano confirma o pedido e informa a chave Pix "
                    "pelos canais de atendimento."
                ),
                "method": "pix",
                "status": "pending",
            },
        )

    def _prepare_manual_delivery(
        self,
        order: dict[str, Any],
        payment_method: str,
    ) -> PaymentPreparation:
        labels = {
            "cash": "Pagamento em dinheiro na entrega",
            "credit_card": "Cartao de credito na entrega",
            "debit_card": "Cartao de debito na entrega",
        }
        return PaymentPreparation(
            provider=PaymentProvider.MANUAL,
            reference=str(order.get("id") or ""),
            payload={
                "title": labels.get(payment_method, "Pagamento na entrega"),
                "description": "Pagamento sera confirmado pela equipe no atendimento.",
                "method": payment_method,
                "status": "pending",
            },
        )

    def _prepare_pix_static(self, order: dict[str, Any]) -> PaymentPreparation:
        if not settings.pix_key:
            return self._prepare_manual_pix(order)

        order_id = str(order.get("id") or "")
        txid = normalize_txid(f"{settings.pix_txid_prefix}{order_id[:12]}")
        total = Decimal(str(order.get("total") or "0"))
        expires_at = datetime.now(tz=UTC) + timedelta(
            minutes=settings.pix_expires_minutes,
        )
        copy_paste = build_pix_copy_paste(
            pix_key=settings.pix_key,
            merchant_name=settings.pix_merchant_name,
            merchant_city=settings.pix_merchant_city,
            amount=total,
            txid=txid,
            description=f"Pedido Lugano {order_id[:8]}",
        )
        return PaymentPreparation(
            provider=PaymentProvider.PIX_STATIC,
            reference=txid,
            payload={
                "title": "Pix copia e cola",
                "description": (
                    "Pague pelo Pix copia e cola e aguarde a confirmacao manual "
                    "da equipe Lugano."
                ),
                "method": "pix",
                "status": "pending",
                "pix_key": settings.pix_key,
                "pix_copy_paste": copy_paste,
                "amount": f"{total:.2f}",
                "txid": txid,
                "expires_at": expires_at.isoformat(),
            },
        )
