from __future__ import annotations

import base64
import logging
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx

from app.core.config import settings
from app.services.monitoring import send_monitoring_alert
from supabase import Client

logger = logging.getLogger("lugano.delivery")


@dataclass(frozen=True)
class DeliveryQuote:
    provider: str
    delivery_fee_cents: int
    external_quote_id: str | None = None
    estimated_minutes: int | None = None
    raw_response: dict[str, Any] | None = None


@dataclass(frozen=True)
class DeliveryDispatch:
    provider: str
    status: str
    external_delivery_id: str | None = None
    external_quote_id: str | None = None
    tracking_url: str | None = None
    raw_response: dict[str, Any] | None = None


class DeliveryProviderError(RuntimeError):
    pass


MACHINE_STATUS_LABELS = {
    "D": "distributing",
    "G": "waiting_acceptance",
    "A": "accepted",
    "S": "waiting",
    "E": "in_progress",
    "F": "finished",
    "N": "not_served",
    "C": "cancelled",
    "P": "pending",
}


def money_to_cents(value: Any) -> int:
    amount = Decimal(str(value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


class ManualDeliveryProvider:
    provider = "manual"

    async def quote(
        self,
        *,
        subtotal_cents: int,
        free_delivery: bool = False,
        address: dict[str, Any] | None = None,
    ) -> DeliveryQuote:
        delivery_fee = (
            0
            if free_delivery or subtotal_cents >= settings.delivery_free_threshold
            else settings.delivery_base_fee
        )
        return DeliveryQuote(
            provider=self.provider,
            delivery_fee_cents=delivery_fee,
            raw_response={
                "mode": "manual",
                "subtotal_cents": subtotal_cents,
                "free_delivery": free_delivery,
                "address_id": (address or {}).get("id"),
            },
        )

    async def dispatch(
        self,
        *,
        order: dict[str, Any],
        customer: dict[str, Any] | None,
        address: dict[str, Any] | None,
        items: list[dict[str, Any]],
    ) -> DeliveryDispatch:
        return DeliveryDispatch(
            provider=self.provider,
            status="manual_pending",
            raw_response={
                "mode": "manual",
                "order_id": order.get("id"),
                "customer_id": (customer or {}).get("id"),
                "address_id": (address or {}).get("id"),
                "items_count": len(items),
            },
        )


class ExternalApiDeliveryProvider:
    provider = "external_api"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if settings.delivery_api_auth_header == "Authorization":
            headers["Authorization"] = f"Bearer {settings.delivery_api_key}"
        else:
            headers["X-API-Key"] = settings.delivery_api_key or ""
        return headers

    def _url(self, path: str) -> str:
        if not settings.delivery_api_base_url:
            raise DeliveryProviderError("DELIVERY_API_BASE_URL nao configurado")
        base_url = settings.delivery_api_base_url.rstrip("/")
        return f"{base_url}/{path.lstrip('/')}"

    async def quote(
        self,
        *,
        subtotal_cents: int,
        free_delivery: bool = False,
        address: dict[str, Any] | None = None,
    ) -> DeliveryQuote:
        payload = {
            "subtotal_cents": subtotal_cents,
            "free_delivery": free_delivery,
            "address": address or {},
        }
        data = await self._post(settings.delivery_api_quote_path, payload)
        return DeliveryQuote(
            provider=self.provider,
            delivery_fee_cents=int(
                data.get("delivery_fee_cents")
                or data.get("fee_cents")
                or data.get("fee")
                or 0
            ),
            external_quote_id=data.get("quote_id") or data.get("id"),
            estimated_minutes=data.get("estimated_minutes"),
            raw_response=data,
        )

    async def dispatch(
        self,
        *,
        order: dict[str, Any],
        customer: dict[str, Any] | None,
        address: dict[str, Any] | None,
        items: list[dict[str, Any]],
    ) -> DeliveryDispatch:
        payload = {
            "order": order,
            "customer": customer or {},
            "address": address or {},
            "items": items,
        }
        data = await self._post(settings.delivery_api_dispatch_path, payload)
        return DeliveryDispatch(
            provider=self.provider,
            status=str(data.get("status") or "requested"),
            external_delivery_id=data.get("delivery_id") or data.get("id"),
            external_quote_id=data.get("quote_id"),
            tracking_url=data.get("tracking_url"),
            raw_response=data,
        )

    async def cancel(self, *, external_delivery_id: str) -> dict[str, Any]:
        path = settings.delivery_api_cancel_path.format(
            external_delivery_id=external_delivery_id,
        )
        return await self._post(path, {"external_delivery_id": external_delivery_id})

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=settings.delivery_api_timeout_seconds,
            ) as client:
                response = await client.post(
                    self._url(path),
                    json=payload,
                    headers=self._headers(),
                )
            response.raise_for_status()
            if not response.content:
                return {}
            data = response.json()
            if not isinstance(data, dict):
                raise DeliveryProviderError("Resposta da API de entrega nao e JSON")
            return data
        except DeliveryProviderError:
            raise
        except Exception as exc:
            raise DeliveryProviderError(str(exc)) from exc


class MachineDeliveryProvider:
    provider = "machine"

    def _headers(self, *, content_type: bool = True) -> dict[str, str]:
        username = settings.delivery_api_username or ""
        password = settings.delivery_api_password or ""
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode(
            "ascii"
        )
        headers = {
            "Authorization": f"Basic {token}",
            "api-key": settings.delivery_api_key or "",
        }
        if content_type:
            headers["Content-Type"] = "application/json"
        return headers

    def _url(self, path: str) -> str:
        if not settings.delivery_api_base_url:
            raise DeliveryProviderError("DELIVERY_API_BASE_URL nao configurado")
        base_url = settings.delivery_api_base_url.rstrip("/")
        return f"{base_url}/{path.lstrip('/')}"

    def _origin_payload(self) -> dict[str, Any]:
        payload = {
            "endereco": settings.delivery_origin_address,
            "bairro": settings.delivery_origin_neighborhood,
            "complemento": settings.delivery_origin_complement,
            "cidade": settings.delivery_origin_city,
            "estado": settings.delivery_origin_state,
            "referencia": settings.delivery_origin_reference,
        }
        if settings.delivery_origin_lat is not None:
            payload["lat"] = str(settings.delivery_origin_lat)
        if settings.delivery_origin_lng is not None:
            payload["lng"] = str(settings.delivery_origin_lng)
        return {key: value for key, value in payload.items() if value not in (None, "")}

    def _destination_payload(
        self,
        *,
        order: dict[str, Any] | None,
        customer: dict[str, Any] | None,
        address: dict[str, Any] | None,
    ) -> dict[str, Any]:
        address = address or {}
        customer = customer or {}
        street = str(address.get("street") or "").strip()
        number = str(address.get("number") or "").strip()
        destination = {
            "endereco_parada": self._join_address(street, number),
            "bairro_parada": address.get("neighborhood"),
            "complemento_parada": address.get("complement"),
            "cidade_parada": address.get("city"),
            "estado_parada": address.get("state")
            or settings.delivery_default_destination_state,
            "referencia_parada": address.get("label"),
            "id_externo": str((order or {}).get("id") or ""),
            "observacao_parada": (order or {}).get("notes"),
            "nome_cliente_parada": customer.get("full_name") or customer.get("email"),
            "telefone_cliente_parada": customer.get("phone"),
            "valor_cobrar": float(Decimal(str((order or {}).get("total") or "0"))),
        }
        lat = address.get("lat") or address.get("latitude")
        lng = address.get("lng") or address.get("longitude")
        if lat is not None:
            destination["lat_parada"] = str(lat)
        if lng is not None:
            destination["lng_parada"] = str(lng)
        return {
            key: value
            for key, value in destination.items()
            if value not in (None, "")
        }

    def _quote_payload(self, address: dict[str, Any] | None) -> dict[str, Any]:
        destination = self._destination_payload(order=None, customer=None, address=address)
        payload = {
            "endereco_partida": settings.delivery_origin_address,
            "bairro_partida": settings.delivery_origin_neighborhood,
            "cidade_partida": settings.delivery_origin_city,
            "estado_partida": settings.delivery_origin_state,
            "endereco_desejado": destination.get("endereco_parada"),
            "bairro_desejado": destination.get("bairro_parada"),
            "cidade_desejado": destination.get("cidade_parada"),
            "estado_desejado": destination.get("estado_parada"),
            "categoria_id": settings.delivery_machine_category_id,
            "categoria_nome": settings.delivery_machine_category_name,
            "com_retorno": False,
        }
        if settings.delivery_origin_lat is not None:
            payload["lat_partida"] = settings.delivery_origin_lat
        if settings.delivery_origin_lng is not None:
            payload["lng_partida"] = settings.delivery_origin_lng
        if "lat_parada" in destination:
            payload["lat_desejado"] = float(destination["lat_parada"])
        if "lng_parada" in destination:
            payload["lng_desejado"] = float(destination["lng_parada"])
        return {key: value for key, value in payload.items() if value not in (None, "")}

    def _dispatch_payload(
        self,
        *,
        order: dict[str, Any],
        customer: dict[str, Any] | None,
        address: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload = {
            "forma_pagamento": settings.delivery_machine_payment_method,
            "partida": self._origin_payload(),
            "paradas": [
                self._destination_payload(
                    order=order,
                    customer=customer,
                    address=address,
                )
            ],
        }
        if settings.delivery_machine_category_id is not None:
            payload["categoria_id"] = settings.delivery_machine_category_id
        if settings.delivery_machine_category_name:
            payload["categoria_nome"] = settings.delivery_machine_category_name
        return payload

    def _join_address(self, street: str, number: str) -> str:
        if street and number:
            return f"{street}, {number}"
        return street or number

    def _extract_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("success") is False:
            errors = payload.get("errors") or payload.get("message") or payload
            raise DeliveryProviderError(f"Machine recusou a requisicao: {errors}")
        data = payload.get("data", payload)
        if isinstance(data, list):
            return {"items": data}
        if not isinstance(data, dict):
            return {}
        return data

    async def quote(
        self,
        *,
        subtotal_cents: int,
        free_delivery: bool = False,
        address: dict[str, Any] | None = None,
    ) -> DeliveryQuote:
        if free_delivery:
            return DeliveryQuote(
                provider=self.provider,
                delivery_fee_cents=0,
                raw_response={"free_delivery": True},
            )
        data = await self._post(settings.delivery_api_quote_path, self._quote_payload(address))
        machine_data = self._extract_data(data)
        return DeliveryQuote(
            provider=self.provider,
            delivery_fee_cents=money_to_cents(machine_data.get("estimativa_valor")),
            estimated_minutes=machine_data.get("estimativa_minutos"),
            raw_response=data,
        )

    async def dispatch(
        self,
        *,
        order: dict[str, Any],
        customer: dict[str, Any] | None,
        address: dict[str, Any] | None,
        items: list[dict[str, Any]],
    ) -> DeliveryDispatch:
        data = await self._post(
            settings.delivery_api_dispatch_path,
            self._dispatch_payload(order=order, customer=customer, address=address),
        )
        machine_data = self._extract_data(data)
        external_delivery_id = self._external_id(machine_data)
        tracking_url = await self._tracking_url(external_delivery_id)
        status = MACHINE_STATUS_LABELS.get(str(machine_data.get("status") or ""), "requested")
        return DeliveryDispatch(
            provider=self.provider,
            status=status,
            external_delivery_id=external_delivery_id,
            tracking_url=tracking_url,
            raw_response=data,
        )

    async def cancel(self, *, external_delivery_id: str) -> dict[str, Any]:
        if not settings.delivery_machine_cancel_reason_id:
            raise DeliveryProviderError("DELIVERY_MACHINE_CANCEL_REASON_ID nao configurado")
        path = settings.delivery_api_cancel_path.format(
            external_delivery_id=external_delivery_id,
        )
        return await self._post(
            path,
            {"motivo_id": settings.delivery_machine_cancel_reason_id},
        )

    async def get_status(self, *, external_delivery_id: str) -> str | None:
        path = settings.delivery_api_status_path.format(
            external_delivery_id=external_delivery_id,
        )
        data = await self._get(path)
        machine_data = self._extract_data(data)
        status = str(machine_data.get("status") or "")
        return MACHINE_STATUS_LABELS.get(status, status or None)

    async def _tracking_url(self, external_delivery_id: str | None) -> str | None:
        if not external_delivery_id:
            return None
        try:
            path = settings.delivery_api_tracking_path.format(
                external_delivery_id=external_delivery_id,
            )
            data = await self._get(path)
            machine_data = self._extract_data(data)
            items = machine_data.get("items") or []
            first_item = items[0] if items else {}
            return first_item.get("link_rastreio")
        except Exception:
            logger.exception(
                "Failed to fetch Machine tracking link delivery_id=%s",
                external_delivery_id,
            )
            return None

    def _external_id(self, data: dict[str, Any]) -> str | None:
        for key in ("id", "solicitacao_id", "entrega_id", "pedido_id", "codigo"):
            value = data.get(key)
            if value is not None:
                return str(value)
        return None

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=settings.delivery_api_timeout_seconds,
            ) as client:
                response = await client.post(
                    self._url(path),
                    json=payload,
                    headers=self._headers(),
                )
            return self._decode_response(response)
        except DeliveryProviderError:
            raise
        except Exception as exc:
            raise DeliveryProviderError(str(exc)) from exc

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=settings.delivery_api_timeout_seconds,
            ) as client:
                response = await client.get(
                    self._url(path),
                    headers=self._headers(content_type=False),
                )
            return self._decode_response(response)
        except DeliveryProviderError:
            raise
        except Exception as exc:
            raise DeliveryProviderError(str(exc)) from exc

    def _decode_response(self, response: httpx.Response) -> dict[str, Any]:
        if response.is_error:
            detail = self._response_error_detail(response)
            message = (
                f"Machine retornou {response.status_code} "
                f"{response.reason_phrase}"
            )
            if detail:
                message = f"{message}: {detail}"
            raise DeliveryProviderError(message)

        if not response.content:
            return {}
        data = response.json()
        if not isinstance(data, dict):
            raise DeliveryProviderError("Resposta da API Machine nao e JSON")
        return data

    def _response_error_detail(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            data = response.text

        if isinstance(data, dict):
            detail = data.get("message") or data.get("error") or data.get("errors") or data
        else:
            detail = data

        text = str(detail).strip()
        if not text:
            return ""
        text = " ".join(text.split())
        if len(text) > 700:
            text = f"{text[:700]}..."
        return text


def get_delivery_provider():
    if settings.delivery_provider == "machine":
        return MachineDeliveryProvider()
    if settings.delivery_provider == "external_api":
        return ExternalApiDeliveryProvider()
    return ManualDeliveryProvider()


class DeliveryService:
    def __init__(self, db: Client | None = None):
        self.db = db
        self.provider = get_delivery_provider()

    async def quote(
        self,
        *,
        subtotal_cents: int,
        free_delivery: bool = False,
        address: dict[str, Any] | None = None,
    ) -> DeliveryQuote:
        return await self.provider.quote(
            subtotal_cents=subtotal_cents,
            free_delivery=free_delivery,
            address=address,
        )

    async def safe_dispatch_order(
        self,
        *,
        order: dict[str, Any],
        customer: dict[str, Any] | None,
        address: dict[str, Any] | None,
        items: list[dict[str, Any]],
    ) -> DeliveryDispatch | None:
        if not settings.delivery_auto_dispatch_enabled:
            return None

        try:
            dispatch = await self.provider.dispatch(
                order=order,
                customer=customer,
                address=address,
                items=items,
            )
            self._record_dispatch(order=order, dispatch=dispatch)
            return dispatch
        except Exception as exc:
            order_id = str(order.get("id") or "")
            logger.exception("Delivery dispatch failed order_id=%s", order_id)
            self._record_dispatch_error(order=order, error=str(exc))
            await send_monitoring_alert(
                title="Falha ao solicitar entrega",
                message=f"Erro ao integrar entrega do pedido {order_id}: {exc}",
                severity="warning",
                metadata={
                    "order_id": order_id,
                    "provider": settings.delivery_provider,
                    "check": "delivery_dispatch",
                },
            )
            return None

    def _record_dispatch(
        self,
        *,
        order: dict[str, Any],
        dispatch: DeliveryDispatch,
    ) -> None:
        if not self.db:
            return
        self.db.table("delivery_dispatches").insert(
            {
                "order_id": order.get("id"),
                "provider": dispatch.provider,
                "status": dispatch.status,
                "external_delivery_id": dispatch.external_delivery_id,
                "external_quote_id": dispatch.external_quote_id,
                "tracking_url": dispatch.tracking_url,
                "request_payload": {"order_id": order.get("id")},
                "response_payload": dispatch.raw_response or asdict(dispatch),
                "dispatched_at": None
                if dispatch.status == "manual_pending"
                else order.get("placed_at"),
            }
        ).execute()

    def _record_dispatch_error(self, *, order: dict[str, Any], error: str) -> None:
        if not self.db:
            return
        try:
            self.db.table("delivery_dispatches").insert(
                {
                    "order_id": order.get("id"),
                    "provider": settings.delivery_provider,
                    "status": "failed",
                    "request_payload": {"order_id": order.get("id")},
                    "response_payload": {},
                    "error": error,
                }
            ).execute()
        except Exception:
            logger.exception(
                "Failed to record delivery dispatch error order_id=%s",
                order.get("id"),
            )
