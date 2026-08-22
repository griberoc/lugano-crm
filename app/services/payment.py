from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

import httpx

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


class PaymentProviderError(RuntimeError):
    pass


class PaymentNotFoundError(PaymentProviderError):
    pass


MERCADO_PAGO_STATUS_MAP = {
    "approved": "paid",
    "accredited": "paid",
    "cancelled": "failed",
    "charged_back": "refunded",
    "refunded": "refunded",
    "rejected": "failed",
}

FINAL_PAYMENT_STATUSES = {"paid", "refunded"}


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


def map_mercado_pago_status(status: str | None) -> str:
    return MERCADO_PAGO_STATUS_MAP.get(str(status or "").lower(), "pending")


def verify_mercado_pago_signature(
    *,
    x_signature: str | None,
    x_request_id: str | None,
    data_id: str | None,
    secret: str | None,
) -> bool:
    if not secret:
        return True
    if not x_signature or not x_request_id:
        return False

    signature_parts = {}
    for part in x_signature.split(","):
        key, _, value = part.partition("=")
        if key and value:
            signature_parts[key.strip()] = value.strip()

    timestamp = signature_parts.get("ts")
    received_hash = signature_parts.get("v1")
    if not timestamp or not received_hash:
        return False

    manifest_parts = []
    if data_id:
        manifest_parts.append(f"id:{str(data_id).lower()}")
    manifest_parts.append(f"request-id:{x_request_id}")
    manifest_parts.append(f"ts:{timestamp}")
    manifest = ";".join(manifest_parts) + ";"
    expected_hash = hmac.new(
        secret.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_hash, received_hash)


class PaymentService:
    def prepare(
        self,
        order: dict[str, Any],
        payment_method: str,
        customer: dict[str, Any] | None = None,
    ) -> PaymentPreparation:
        if payment_method == "pix" and settings.payment_provider == "mercado_pago":
            return self._prepare_mercado_pago_pix(order, customer=customer)

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

    def _prepare_mercado_pago_pix(
        self,
        order: dict[str, Any],
        *,
        customer: dict[str, Any] | None,
    ) -> PaymentPreparation:
        if not settings.mercado_pago_access_token:
            return self._prepare_manual_pix(order)

        payer_email = (customer or {}).get("email") or order.get("customer_email")
        if not payer_email:
            raise PaymentProviderError(
                "Email do cliente e obrigatorio para criar Pix Mercado Pago"
            )

        order_id = str(order.get("id") or "")
        total = Decimal(str(order.get("total") or "0")).quantize(Decimal("0.01"))
        request_payload = {
            "transaction_amount": float(total),
            "description": f"Pedido Lugano {order_id[:8]}",
            "payment_method_id": "pix",
            "external_reference": order_id,
            "payer": {"email": payer_email},
        }
        if settings.mercado_pago_notification_url:
            request_payload["notification_url"] = settings.mercado_pago_notification_url

        response = self._request_mercado_pago(
            "POST",
            "/v1/payments",
            json=request_payload,
            idempotency_key=f"lugano-order-{order_id}",
        )
        payment_id = str(response.get("id") or "")
        transaction_data = (
            response.get("point_of_interaction", {})
            .get("transaction_data", {})
        )
        pix_copy_paste = transaction_data.get("qr_code")
        pix_qr_code_base64 = transaction_data.get("qr_code_base64")
        ticket_url = transaction_data.get("ticket_url")
        mapped_status = map_mercado_pago_status(response.get("status"))

        return PaymentPreparation(
            provider=PaymentProvider.MERCADO_PAGO,
            reference=payment_id or order_id,
            payload={
                "title": "Pix Mercado Pago",
                "description": (
                    "Pague pelo Pix gerado pelo Mercado Pago. A confirmacao "
                    "sera atualizada automaticamente apos o pagamento."
                ),
                "method": "pix",
                "status": mapped_status,
                "amount": f"{total:.2f}",
                "mercado_pago_payment_id": payment_id or None,
                "external_reference": order_id,
                "status_detail": response.get("status_detail"),
                "pix_copy_paste": pix_copy_paste,
                "pix_qr_code_base64": pix_qr_code_base64,
                "payment_url": ticket_url,
                "raw_status": response.get("status"),
            },
        )

    def get_mercado_pago_payment(self, payment_id: str) -> dict[str, Any]:
        return self._request_mercado_pago("GET", f"/v1/payments/{payment_id}")

    def sync_mercado_pago_payment(
        self,
        *,
        db,
        payment_id: str,
    ) -> dict[str, Any]:
        payment = self.get_mercado_pago_payment(payment_id)
        external_reference = str(payment.get("external_reference") or "")
        payment_reference = str(payment.get("id") or payment_id)

        order = self._find_order_for_payment(
            db=db,
            external_reference=external_reference,
            payment_reference=payment_reference,
        )
        if not order:
            return {
                "updated": False,
                "reason": "order_not_found",
                "payment_id": payment_reference,
                "external_reference": external_reference,
            }


        validation_error = self._validate_mercado_pago_payment(
            order=order,
            payment=payment,
        )
        if validation_error:
            return {
                "updated": False,
                "reason": validation_error,
                "order_id": order["id"],
                "payment_id": payment_reference,
            }

        previous_payload = order.get("payment_payload") or {}
        if not isinstance(previous_payload, dict):
            previous_payload = {}

        transaction_data = (
            payment.get("point_of_interaction", {})
            .get("transaction_data", {})
        )
        next_payload = {
            **previous_payload,
            "status": map_mercado_pago_status(payment.get("status")),
            "raw_status": payment.get("status"),
            "status_detail": payment.get("status_detail"),
            "mercado_pago_payment_id": payment_reference,
            "external_reference": external_reference or order.get("id"),
        }
        if transaction_data.get("qr_code"):
            next_payload["pix_copy_paste"] = transaction_data["qr_code"]
        if transaction_data.get("qr_code_base64"):
            next_payload["pix_qr_code_base64"] = transaction_data["qr_code_base64"]
        if transaction_data.get("ticket_url"):
            next_payload["payment_url"] = transaction_data["ticket_url"]

        payment_status = map_mercado_pago_status(payment.get("status"))
        previous_status = str(order.get("payment_status") or "pending")
        if (
            previous_status in FINAL_PAYMENT_STATUSES
            and payment_status != previous_status
        ):
            return {
                "updated": False,
                "reason": "stale_payment_status",
                "order_id": order["id"],
                "payment_id": payment_reference,
                "payment_status": previous_status,
            }

        changed = payment_status != previous_status or next_payload != previous_payload
        if not changed:
            return {
                "updated": False,
                "changed": False,
                "reason": "duplicate_event",
                "order_id": order["id"],
                "payment_id": payment_reference,
                "payment_status": previous_status,
            }
        updates = {
            "payment_status": payment_status,
            "payment_reference": payment_reference,
            "payment_payload": next_payload,
        }
        if payment_status == "paid":
            updates["paid_at"] = payment.get("date_approved") or datetime.now(
                UTC
            ).isoformat()

        db.table("orders").update(updates).eq("id", order["id"]).execute()
        return {
            "updated": True,
            "changed": changed,
            "order_id": order["id"],
            "payment_id": payment_reference,
            "payment_status": payment_status,
        }

    def _find_order_for_payment(
        self,
        *,
        db,
        external_reference: str,
        payment_reference: str,
    ) -> dict[str, Any] | None:
        if external_reference:
            response = (
                db.table("orders")
                .select("id,total,payment_provider,payment_status,payment_payload")
                .eq("id", external_reference)
                .eq("payment_provider", PaymentProvider.MERCADO_PAGO.value)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]

        response = (
            db.table("orders")
            .select("id,total,payment_provider,payment_status,payment_payload")
            .eq("payment_provider", PaymentProvider.MERCADO_PAGO.value)
            .eq("payment_reference", payment_reference)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def _validate_mercado_pago_payment(
        self,
        *,
        order: dict[str, Any],
        payment: dict[str, Any],
    ) -> str | None:
        if payment.get("currency_id") not in (None, "BRL"):
            return "currency_mismatch"

        transaction_amount = payment.get("transaction_amount")
        if transaction_amount is None:
            return "missing_transaction_amount"
        try:
            expected = Decimal(str(order.get("total") or "0")).quantize(
                Decimal("0.01")
            )
            received = Decimal(str(transaction_amount)).quantize(Decimal("0.01"))
        except InvalidOperation:
            return "invalid_transaction_amount"
        if received != expected:
            return "amount_mismatch"
        return None

    def _request_mercado_pago(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if not settings.mercado_pago_access_token:
            raise PaymentProviderError("MERCADO_PAGO_ACCESS_TOKEN nao configurado")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.mercado_pago_access_token}",
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        url = f"{settings.mercado_pago_base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=settings.mercado_pago_timeout_seconds) as client:
                response = client.request(method, url, json=json, headers=headers)
            return self._decode_mercado_pago_response(response)
        except PaymentProviderError:
            raise
        except Exception as exc:
            raise PaymentProviderError(str(exc)) from exc

    def _decode_mercado_pago_response(self, response: httpx.Response) -> dict[str, Any]:
        if response.is_error:
            detail = self._mercado_pago_error_detail(response)
            message = (
                f"Mercado Pago retornou {response.status_code} "
                f"{response.reason_phrase}"
            )
            if detail:
                message = f"{message}: {detail}"
            if response.status_code == 404:
                raise PaymentNotFoundError(message)
            raise PaymentProviderError(message)
        if not response.content:
            return {}
        data = response.json()
        if not isinstance(data, dict):
            raise PaymentProviderError("Resposta do Mercado Pago nao e JSON")
        return data

    def _mercado_pago_error_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            data = response.text

        if isinstance(data, dict):
            detail = (
                data.get("message")
                or data.get("error")
                or data.get("cause")
                or data
            )
        else:
            detail = data

        text = str(detail).strip()
        if not text:
            return ""
        text = " ".join(text.split())
        if len(text) > 700:
            text = f"{text[:700]}..."
        return text
