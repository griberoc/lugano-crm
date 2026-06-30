import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("lugano.monitoring")


async def send_monitoring_alert(
    *,
    title: str,
    message: str,
    severity: str,
    metadata: dict[str, Any] | None = None,
) -> bool:
    if not settings.monitoring_alerts_enabled:
        return False

    if not settings.monitoring_webhook_url:
        logger.warning(
            "Monitoring alert not sent because MONITORING_WEBHOOK_URL is empty "
            "severity=%s title=%s",
            severity,
            title,
        )
        return False

    headers = {"Content-Type": "application/json"}
    if settings.monitoring_webhook_token:
        headers["Authorization"] = f"Bearer {settings.monitoring_webhook_token}"

    payload = {
        "service": settings.monitoring_service_name,
        "environment": settings.app_env,
        "severity": severity,
        "title": title,
        "message": message,
        "metadata": metadata or {},
        "created_at": datetime.now(tz=UTC).isoformat(),
    }

    try:
        async with httpx.AsyncClient(
            timeout=settings.monitoring_webhook_timeout_seconds,
        ) as client:
            response = await client.post(
                settings.monitoring_webhook_url,
                json=payload,
                headers=headers,
            )
        response.raise_for_status()
    except Exception:
        logger.exception(
            "Failed to send monitoring alert severity=%s title=%s",
            severity,
            title,
        )
        return False

    logger.info("Monitoring alert sent severity=%s title=%s", severity, title)
    return True
