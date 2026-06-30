import argparse
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]


class MonitorError(RuntimeError):
    pass


@dataclass(frozen=True)
class MonitorConfig:
    api_base_url: str
    environment: str = "production"
    service_name: str = "lugano-crm"
    health_path: str = "/health/ready"
    timeout_seconds: float = 10.0
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    failed_notification_window_minutes: int = 60
    failed_notification_limit: int = 20
    monitoring_webhook_url: str | None = None
    monitoring_webhook_token: str | None = None


def load_dotenv(path: Path, *, override: bool = False) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override:
            os.environ[key] = value
        else:
            os.environ.setdefault(key, value)


def env_or_arg(
    value: str | None,
    env_name: str,
    *,
    required: bool = True,
) -> str | None:
    result = value or os.getenv(env_name)
    if required and not result:
        raise MonitorError(
            f"Missing {env_name}. Provide CLI option or environment value."
        )
    return result


def parse_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def service_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def utc_since(minutes: int) -> str:
    since = datetime.now(UTC) - timedelta(minutes=minutes)
    return since.isoformat().replace("+00:00", "Z")


def check_api_health(client: httpx.Client, config: MonitorConfig) -> dict[str, Any]:
    try:
        response = client.get(config.health_path)
    except httpx.HTTPError as exc:
        raise MonitorError(f"API healthcheck failed: {exc}") from exc

    body = parse_body(response)
    if response.status_code != 200:
        raise MonitorError(
            f"API healthcheck returned {response.status_code}: {body}"
        )
    if isinstance(body, dict) and body.get("status") not in {"ok", "ready"}:
        raise MonitorError(f"API healthcheck status is not ok: {body}")
    return body if isinstance(body, dict) else {"body": body}


def fetch_failed_notifications(
    client: httpx.Client,
    config: MonitorConfig,
) -> list[dict[str, Any]]:
    if not config.supabase_url or not config.supabase_service_role_key:
        return []

    response = client.get(
        "/rest/v1/notification_events",
        headers=service_headers(config.supabase_service_role_key),
        params={
            "select": "id,event_type,channel,order_id,error,created_at,status",
            "status": "eq.failed",
            "created_at": f"gte.{utc_since(config.failed_notification_window_minutes)}",
            "order": "created_at.desc",
            "limit": str(config.failed_notification_limit),
        },
    )
    body = parse_body(response)
    if response.status_code != 200:
        raise MonitorError(
            f"Failed notification query returned {response.status_code}: {body}"
        )
    if not isinstance(body, list):
        raise MonitorError(f"Unexpected failed notification response: {body}")
    return body


def send_alert(
    client: httpx.Client,
    config: MonitorConfig,
    *,
    title: str,
    message: str,
    severity: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    payload = {
        "service": config.service_name,
        "environment": config.environment,
        "severity": severity,
        "title": title,
        "message": message,
        "metadata": metadata or {},
        "created_at": datetime.now(UTC).isoformat(),
    }

    if not config.monitoring_webhook_url:
        print(f"[ALERT:{severity}] {title} - {message}")
        return

    headers = {"Content-Type": "application/json"}
    if config.monitoring_webhook_token:
        headers["Authorization"] = f"Bearer {config.monitoring_webhook_token}"

    response = client.post(
        config.monitoring_webhook_url,
        json=payload,
        headers=headers,
    )
    body = parse_body(response)
    if response.status_code >= 400:
        raise MonitorError(
            f"Monitoring webhook returned {response.status_code}: {body}"
        )


def run_monitor_with_clients(
    config: MonitorConfig,
    *,
    api: httpx.Client,
    supabase: httpx.Client,
    alerts: httpx.Client,
) -> None:
    failures: list[str] = []

    try:
        health = check_api_health(api, config)
        print(f"[OK] API health: {health}")
    except MonitorError as exc:
        failures.append(str(exc))
        send_alert(
            alerts,
            config,
            title="API Lugano indisponivel",
            message=str(exc),
            severity="critical",
            metadata={"check": "api_health", "health_path": config.health_path},
        )

    try:
        failed_notifications = fetch_failed_notifications(supabase, config)
    except MonitorError as exc:
        failures.append(str(exc))
        send_alert(
            alerts,
            config,
            title="Falha ao consultar notificacoes",
            message=str(exc),
            severity="warning",
            metadata={"check": "failed_notifications"},
        )
    else:
        if failed_notifications:
            message = (
                f"{len(failed_notifications)} notificacao(oes) falharam nos "
                f"ultimos {config.failed_notification_window_minutes} minutos."
            )
            failures.append(message)
            send_alert(
                alerts,
                config,
                title="Notificacoes com falha",
                message=message,
                severity="warning",
                metadata={
                    "check": "failed_notifications",
                    "events": failed_notifications,
                },
            )
        else:
            print("[OK] Notificacoes sem falhas recentes")

    if failures:
        raise MonitorError("; ".join(failures))


def run_monitor(config: MonitorConfig) -> None:
    with (
        httpx.Client(
            base_url=config.api_base_url.rstrip("/"),
            timeout=config.timeout_seconds,
        ) as api,
        httpx.Client(
            base_url=(config.supabase_url or "https://supabase.local").rstrip("/"),
            timeout=config.timeout_seconds,
        ) as supabase,
        httpx.Client(timeout=config.timeout_seconds) as alerts,
    ):
        run_monitor_with_clients(
            config,
            api=api,
            supabase=supabase,
            alerts=alerts,
        )


def build_config(args: argparse.Namespace) -> MonitorConfig:
    timeout_seconds = float(args.timeout_seconds)
    if timeout_seconds <= 0:
        raise MonitorError("timeout_seconds must be greater than 0.")

    window_minutes = int(args.failed_notification_window_minutes)
    if window_minutes < 1:
        raise MonitorError("failed_notification_window_minutes must be at least 1.")

    limit = int(args.failed_notification_limit)
    if limit < 1 or limit > 100:
        raise MonitorError("failed_notification_limit must be between 1 and 100.")

    return MonitorConfig(
        api_base_url=env_or_arg(args.api_base_url, "API_BASE_URL"),
        environment=env_or_arg(
            args.environment,
            "MONITORING_ENVIRONMENT",
            required=False,
        ) or os.getenv("APP_ENV", "production"),
        service_name=env_or_arg(
            args.service_name,
            "MONITORING_SERVICE_NAME",
            required=False,
        ) or "lugano-crm",
        health_path=env_or_arg(
            args.health_path,
            "MONITORING_HEALTH_PATH",
            required=False,
        ) or "/health/ready",
        timeout_seconds=timeout_seconds,
        supabase_url=env_or_arg(
            args.supabase_url,
            "SUPABASE_URL",
            required=False,
        ),
        supabase_service_role_key=env_or_arg(
            args.supabase_service_role_key,
            "SUPABASE_SERVICE_ROLE_KEY",
            required=False,
        ),
        failed_notification_window_minutes=window_minutes,
        failed_notification_limit=limit,
        monitoring_webhook_url=env_or_arg(
            args.monitoring_webhook_url,
            "MONITORING_WEBHOOK_URL",
            required=False,
        ),
        monitoring_webhook_token=env_or_arg(
            args.monitoring_webhook_token,
            "MONITORING_WEBHOOK_TOKEN",
            required=False,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Monitora API e notificacoes do Lugano CRM.",
    )
    parser.add_argument("--env-file", default=".env.production")
    parser.add_argument("--api-base-url")
    parser.add_argument("--environment")
    parser.add_argument("--service-name")
    parser.add_argument("--health-path")
    parser.add_argument("--timeout-seconds", default="10")
    parser.add_argument("--supabase-url")
    parser.add_argument("--supabase-service-role-key")
    parser.add_argument("--failed-notification-window-minutes", default="60")
    parser.add_argument("--failed-notification-limit", default="20")
    parser.add_argument("--monitoring-webhook-url")
    parser.add_argument("--monitoring-webhook-token")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT_DIR / ".env")
    if args.env_file:
        load_dotenv((ROOT_DIR / args.env_file).resolve(), override=True)

    try:
        run_monitor(build_config(args))
    except MonitorError as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"\n[FAIL] HTTP error: {exc}", file=sys.stderr)
        return 1

    print("\nMonitoring check finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
