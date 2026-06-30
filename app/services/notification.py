from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import settings
from app.services.monitoring import send_monitoring_alert
from supabase import Client

logger = logging.getLogger("lugano.notifications")

ORDER_STATUS_EVENTS = {
    "pending": "order_created",
    "confirmed": "order_confirmed",
    "out_for_delivery": "order_out_for_delivery",
    "delivered": "order_delivered",
}

EVENT_SUBJECTS = {
    "order_created": "Pedido recebido pela Lugano",
    "order_confirmed": "Pedido confirmado",
    "order_out_for_delivery": "Pedido saiu para entrega",
    "order_delivered": "Pedido entregue",
}


class NotificationService:
    def __init__(self, db: Client):
        self.db = db

    async def safe_notify_order_status(
        self,
        order: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            return await self.notify_order_status(order)
        except Exception as exc:
            order_id = str(order.get("id") or "")
            logger.exception(
                "Notification dispatch failed order_id=%s status=%s",
                order_id,
                order.get("status"),
            )
            await send_monitoring_alert(
                title="Falha geral de notificacao",
                message=f"Erro ao processar notificacao do pedido {order_id}: {exc}",
                severity="warning",
                metadata={
                    "order_id": order_id,
                    "order_status": order.get("status"),
                    "check": "notification_dispatch",
                },
            )
            return []

    async def notify_order_status(self, order: dict[str, Any]) -> list[dict[str, Any]]:
        if not settings.notifications_enabled:
            return []

        event_type = ORDER_STATUS_EVENTS.get(str(order.get("status") or ""))
        if not event_type:
            return []

        profile = self._get_profile(str(order.get("profile_id") or ""))
        if not profile:
            return []

        subject = EVENT_SUBJECTS[event_type]
        message = self._message(event_type=event_type, order=order, profile=profile)
        events = []

        if settings.notification_email_enabled:
            events.append(
                await self._queue_or_send(
                    channel="email",
                    recipient=profile.get("email"),
                    subject=subject,
                    message=message,
                    event_type=event_type,
                    order=order,
                    profile=profile,
                )
            )

        preferences = profile.get("preferences") or {}
        if not isinstance(preferences, dict):
            preferences = {}
        accepts_whatsapp = preferences.get("accepts_whatsapp", True)
        if settings.notification_whatsapp_enabled and accepts_whatsapp:
            events.append(
                await self._queue_or_send(
                    channel="whatsapp",
                    recipient=profile.get("phone"),
                    subject=subject,
                    message=message,
                    event_type=event_type,
                    order=order,
                    profile=profile,
                )
            )

        return [event for event in events if event]

    def _get_profile(self, profile_id: str) -> dict[str, Any] | None:
        if not profile_id:
            return None
        response = (
            self.db.table("profiles")
            .select("id, full_name, email, phone, preferences")
            .eq("id", profile_id)
            .single()
            .execute()
        )
        return response.data or None

    async def _queue_or_send(
        self,
        *,
        channel: str,
        recipient: str | None,
        subject: str,
        message: str,
        event_type: str,
        order: dict[str, Any],
        profile: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not recipient:
            return self._insert_event(
                channel=channel,
                recipient=None,
                subject=subject,
                message=message,
                event_type=event_type,
                order=order,
                status="skipped",
                error="Recipient missing",
            )

        webhook_url = self._webhook_url(channel)
        if not webhook_url:
            return self._insert_event(
                channel=channel,
                recipient=recipient,
                subject=subject,
                message=message,
                event_type=event_type,
                order=order,
                status="queued",
                provider=self._provider_name(channel),
            )

        event = self._insert_event(
            channel=channel,
            recipient=recipient,
            subject=subject,
            message=message,
            event_type=event_type,
            order=order,
            status="queued",
            provider=self._provider_name(channel),
        )

        payload = {
            "event_type": event_type,
            "channel": channel,
            "recipient": recipient,
            "subject": subject,
            "message": message,
            "order_id": order.get("id"),
            "profile_id": profile.get("id"),
        }
        status_update = await self._send_webhook(channel, webhook_url, payload)
        response = (
            self.db.table("notification_events")
            .update(status_update)
            .eq("id", event["id"])
            .execute()
        )
        return response.data[0] if response.data else event

    def _insert_event(
        self,
        *,
        channel: str,
        recipient: str | None,
        subject: str,
        message: str,
        event_type: str,
        order: dict[str, Any],
        status: str,
        provider: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        response = (
            self.db.table("notification_events")
            .insert(
                {
                    "profile_id": order.get("profile_id"),
                    "order_id": order.get("id"),
                    "event_type": event_type,
                    "channel": channel,
                    "recipient": recipient,
                    "subject": subject,
                    "message": message,
                    "status": status,
                    "provider": provider,
                    "error": error,
                    "attempts": 0,
                }
            )
            .execute()
        )
        return response.data[0]

    async def _send_webhook(
        self,
        channel: str,
        webhook_url: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        token = self._webhook_token(channel)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            async with httpx.AsyncClient(
                timeout=settings.notification_webhook_timeout_seconds,
            ) as client:
                response = await client.post(webhook_url, json=payload, headers=headers)
            response.raise_for_status()
            return {
                "status": "sent",
                "provider_response": {
                    "status_code": response.status_code,
                    "body": response.text[:500],
                },
                "error": None,
                "attempts": 1,
                "sent_at": datetime.now(tz=UTC).isoformat(),
            }
        except Exception as exc:
            error = str(exc)
            logger.exception(
                "Notification webhook failed channel=%s event_type=%s order_id=%s",
                channel,
                payload.get("event_type"),
                payload.get("order_id"),
            )
            await send_monitoring_alert(
                title="Falha ao enviar notificacao",
                message=(
                    f"Webhook de {channel} falhou para pedido "
                    f"{payload.get('order_id')}: {error}"
                ),
                severity="warning",
                metadata={
                    "channel": channel,
                    "event_type": payload.get("event_type"),
                    "order_id": payload.get("order_id"),
                    "profile_id": payload.get("profile_id"),
                    "check": "notification_webhook",
                    "error": error,
                },
            )
            return {
                "status": "failed",
                "provider_response": {},
                "error": error,
                "attempts": 1,
            }

    def _webhook_url(self, channel: str) -> str | None:
        if channel == "email":
            return settings.notification_email_webhook_url
        if channel == "whatsapp":
            return settings.notification_whatsapp_webhook_url
        return None

    def _webhook_token(self, channel: str) -> str | None:
        if channel == "email":
            return settings.notification_email_webhook_token
        if channel == "whatsapp":
            return settings.notification_whatsapp_webhook_token
        return None

    def _provider_name(self, channel: str) -> str:
        return f"{channel}_webhook"

    def _message(
        self,
        *,
        event_type: str,
        order: dict[str, Any],
        profile: dict[str, Any],
    ) -> str:
        name = profile.get("full_name") or "cliente"
        order_id = str(order.get("id") or "")[:8]
        total = self._money(order.get("total"))
        messages = {
            "order_created": (
                f"Ola, {name}! Recebemos seu pedido #{order_id} no valor de "
                f"{total}. Em breve nossa equipe confirma o preparo."
            ),
            "order_confirmed": (
                f"Ola, {name}! Seu pedido #{order_id} foi confirmado e ja "
                "vai seguir para preparo."
            ),
            "order_out_for_delivery": (
                f"Ola, {name}! Seu pedido #{order_id} saiu para entrega."
            ),
            "order_delivered": (
                f"Ola, {name}! Seu pedido #{order_id} foi entregue. "
                "Obrigado por escolher a Lugano."
            ),
        }
        return messages[event_type]

    def _money(self, value: Any) -> str:
        amount = Decimal(str(value or "0"))
        return f"R$ {amount:.2f}".replace(".", ",")
