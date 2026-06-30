import argparse
import os

import httpx
import pytest

from scripts.pre_deploy_check import (
    AuthSession,
    CheckConfig,
    CheckError,
    build_config,
    check_health,
    check_rls,
    load_dotenv,
    request_json,
)


def mock_client(handler):
    return httpx.Client(
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
    )


def test_request_json_raises_with_response_body():
    def handler(_request):
        return httpx.Response(500, json={"detail": "boom"})

    with mock_client(handler) as client:
        with pytest.raises(CheckError) as exc_info:
            request_json(client, "GET", "/health", expected_status=200)

    assert "got 500" in str(exc_info.value)
    assert "boom" in str(exc_info.value)


def test_check_health_validates_expected_env():
    def handler(request):
        assert request.url.path == "/health"
        return httpx.Response(200, json={"status": "ok", "env": "staging"})

    config = CheckConfig(
        api_base_url="https://api.test",
        supabase_url="https://supabase.test",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        admin_email="owner@test",
        admin_password="secret",
        expected_env="staging",
    )

    with mock_client(handler) as client:
        check_health(client, config)


def test_check_rls_passes_expected_guards():
    config = CheckConfig(
        api_base_url="https://api.test",
        supabase_url="https://supabase.test",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        admin_email="owner@test",
        admin_password="secret",
    )
    customer = AuthSession(
        access_token="customer-token",
        user_id="11111111-1111-1111-1111-111111111111",
        email="cliente@test",
    )
    order_id = "22222222-2222-2222-2222-222222222222"

    def handler(request):
        path = request.url.path
        query = dict(request.url.params)
        if path == "/rest/v1/products":
            return httpx.Response(200, json=[{"id": "product-id"}])
        if path == "/rest/v1/orders" and query.get("id") == f"eq.{order_id}":
            return httpx.Response(
                200,
                json=[{"id": order_id, "profile_id": customer.user_id}],
            )
        if path == "/rest/v1/orders":
            return httpx.Response(403, json={"message": "permission denied"})
        if path == "/rest/v1/audit_logs":
            return httpx.Response(403, json={"message": "permission denied"})
        return httpx.Response(404)

    with mock_client(handler) as client:
        check_rls(client, config, customer, order_id)


def test_check_rls_fails_when_anon_can_read_orders():
    config = CheckConfig(
        api_base_url="https://api.test",
        supabase_url="https://supabase.test",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        admin_email="owner@test",
        admin_password="secret",
    )
    customer = AuthSession(access_token="customer-token", user_id="profile-id")

    def handler(request):
        if request.url.path == "/rest/v1/products":
            return httpx.Response(200, json=[])
        if request.url.path == "/rest/v1/orders":
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    with mock_client(handler) as client:
        with pytest.raises(CheckError) as exc_info:
            check_rls(client, config, customer, "order-id")

    assert "should be denied" in str(exc_info.value)


def test_build_config_accepts_customer_access_token(monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://api.test")
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setenv("PREDEPLOY_ADMIN_EMAIL", "owner@test")
    monkeypatch.setenv("PREDEPLOY_ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("PREDEPLOY_CUSTOMER_ACCESS_TOKEN", "customer-token")

    args = argparse.Namespace(
        api_base_url=None,
        supabase_url=None,
        supabase_anon_key=None,
        supabase_service_role_key=None,
        admin_email=None,
        admin_password=None,
        customer_email=None,
        customer_password=None,
        customer_access_token=None,
        expected_env=None,
        keep_order=False,
    )

    config = build_config(args)

    assert config.customer_access_token == "customer-token"
    assert config.expected_env == "staging"


def test_load_dotenv_can_override_existing_values(tmp_path, monkeypatch):
    monkeypatch.setenv("API_BASE_URL", "https://dev.test")
    env_file = tmp_path / ".env.staging"
    env_file.write_text("API_BASE_URL=https://staging.test\n", encoding="utf-8")

    load_dotenv(env_file, override=True)

    assert os.environ["API_BASE_URL"] == "https://staging.test"
