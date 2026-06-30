import argparse

import httpx
import pytest

from scripts.monitor_api import (
    MonitorConfig,
    MonitorError,
    build_config,
    check_api_health,
    fetch_failed_notifications,
    run_monitor_with_clients,
)


def mock_client(base_url, handler):
    return httpx.Client(
        base_url=base_url,
        transport=httpx.MockTransport(handler),
    )


def test_check_api_health_accepts_ready_status():
    def handler(_request):
        return httpx.Response(200, json={"status": "ready", "env": "production"})

    config = MonitorConfig(api_base_url="https://api.test")

    with mock_client("https://api.test", handler) as client:
        health = check_api_health(client, config)

    assert health["status"] == "ready"


def test_check_api_health_rejects_non_200():
    def handler(_request):
        return httpx.Response(503, json={"status": "degraded"})

    config = MonitorConfig(api_base_url="https://api.test")

    with mock_client("https://api.test", handler) as client:
        with pytest.raises(MonitorError):
            check_api_health(client, config)


def test_fetch_failed_notifications_filters_recent_failures():
    def handler(request):
        assert request.url.path == "/rest/v1/notification_events"
        params = dict(request.url.params)
        assert params["status"] == "eq.failed"
        assert params["limit"] == "20"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "notification-id",
                    "status": "failed",
                    "channel": "email",
                }
            ],
        )

    config = MonitorConfig(
        api_base_url="https://api.test",
        supabase_url="https://supabase.test",
        supabase_service_role_key="service-key",
    )

    with mock_client("https://supabase.test", handler) as client:
        events = fetch_failed_notifications(client, config)

    assert events[0]["id"] == "notification-id"


def test_run_monitor_sends_alert_when_api_is_down():
    alert_payloads = []

    def api_handler(_request):
        return httpx.Response(503, json={"status": "degraded"})

    def supabase_handler(_request):
        return httpx.Response(200, json=[])

    def alert_handler(request):
        alert_payloads.append(request.read())
        return httpx.Response(204)

    config = MonitorConfig(
        api_base_url="https://api.test",
        supabase_url="https://supabase.test",
        supabase_service_role_key="service-key",
        monitoring_webhook_url="https://alerts.test/webhook",
    )

    with (
        mock_client("https://api.test", api_handler) as api,
        mock_client("https://supabase.test", supabase_handler) as supabase,
        mock_client("https://alerts.test", alert_handler) as alerts,
    ):
        with pytest.raises(MonitorError):
            run_monitor_with_clients(
                config,
                api=api,
                supabase=supabase,
                alerts=alerts,
            )

    assert alert_payloads


def test_build_config_rejects_invalid_notification_limit(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://api.test")
    args = argparse.Namespace(
        api_base_url=None,
        environment=None,
        service_name=None,
        health_path=None,
        timeout_seconds="10",
        supabase_url=None,
        supabase_service_role_key=None,
        failed_notification_window_minutes="60",
        failed_notification_limit="0",
        monitoring_webhook_url=None,
        monitoring_webhook_token=None,
    )

    with pytest.raises(MonitorError):
        build_config(args)
