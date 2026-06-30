import argparse

import httpx

from scripts.final_security_review import (
    ROOT_DIR,
    SecurityReviewConfig,
    build_config,
    check_allowed_origins,
    has_failures,
    run_review_with_clients,
    validate_origin,
)


def mock_client(base_url, handler):
    return httpx.Client(
        base_url=base_url,
        transport=httpx.MockTransport(handler),
    )


def review_config(**overrides):
    data = {
        "admin_api_key_enabled": "false",
        "allowed_origins": "https://app.lugano.com.br",
        "supabase_url": "https://lugano.supabase.co",
        "supabase_anon_key": "anon-real-key",
        "supabase_service_role_key": "service-real-key",
        "api_base_url": "https://api.lugano.com.br",
        "admin_email": "owner@lugano.com.br",
        "admin_password": "secret-password",
        "frontend_dir": ROOT_DIR / "frontend",
        "migrations_dir": ROOT_DIR / "supabase" / "migrations",
    }
    return SecurityReviewConfig(**{**data, **overrides})


def test_validate_origin_rejects_localhost_and_placeholders():
    assert validate_origin("http://localhost:5176")
    assert validate_origin("https://seu-site.vercel.app")
    assert validate_origin("*")
    assert validate_origin("https://app.lugano.com.br") is None


def test_check_allowed_origins_fails_on_localhost():
    results = []

    check_allowed_origins(
        review_config(allowed_origins="https://app.lugano.com.br,http://localhost:5176"),
        results,
    )

    assert results[0].status == "fail"


def test_run_review_passes_expected_remote_checks():
    def api_handler(request):
        if request.url.path == "/api/v1/admin/login":
            return httpx.Response(
                200,
                json={"admin": {"role": "owner"}},
            )
        return httpx.Response(404)

    def supabase_handler(request):
        path = request.url.path
        params = dict(request.url.params)
        if path == "/rest/v1/profiles" and params.get("email"):
            return httpx.Response(
                200,
                json=[{"id": "owner-id", "email": "owner@lugano.com.br"}],
            )
        if path == "/rest/v1/admin_users" and params.get("profile_id"):
            return httpx.Response(
                200,
                json=[
                    {
                        "profile_id": "owner-id",
                        "role": "owner",
                        "active": True,
                    }
                ],
            )
        if path == "/rest/v1/orders" and request.headers["apikey"] == "anon-real-key":
            return httpx.Response(403, json={"message": "permission denied"})
        if (
            path == "/rest/v1/audit_logs"
            and request.headers["apikey"] == "anon-real-key"
        ):
            return httpx.Response(403, json={"message": "permission denied"})
        if path.startswith("/rest/v1/"):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    config = review_config()
    with (
        mock_client("https://api.lugano.com.br", api_handler) as api,
        mock_client("https://lugano.supabase.co", supabase_handler) as supabase,
    ):
        results = run_review_with_clients(config, api=api, supabase=supabase)

    assert not has_failures(results)
    assert any(result.name == "Owner admin" for result in results)


def test_run_review_fails_when_anon_can_read_orders():
    def api_handler(request):
        if request.url.path == "/api/v1/admin/login":
            return httpx.Response(200, json={"admin": {"role": "owner"}})
        return httpx.Response(404)

    def supabase_handler(request):
        path = request.url.path
        params = dict(request.url.params)
        if path == "/rest/v1/profiles" and params.get("email"):
            return httpx.Response(200, json=[{"id": "owner-id"}])
        if path == "/rest/v1/admin_users" and params.get("profile_id"):
            return httpx.Response(200, json=[{"role": "owner", "active": True}])
        return httpx.Response(200, json=[])

    config = review_config()
    with (
        mock_client("https://api.lugano.com.br", api_handler) as api,
        mock_client("https://lugano.supabase.co", supabase_handler) as supabase,
    ):
        results = run_review_with_clients(config, api=api, supabase=supabase)

    assert has_failures(results)
    assert any(result.name == "RLS basico" for result in results)


def test_build_config_reads_owner_fallback_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_API_KEY_ENABLED", "false")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.lugano.com.br")
    monkeypatch.setenv("SUPABASE_URL", "https://lugano.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service")
    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@lugano.com.br")

    args = argparse.Namespace(
        admin_api_key_enabled=None,
        allowed_origins=None,
        supabase_url=None,
        supabase_anon_key=None,
        supabase_service_role_key=None,
        api_base_url=None,
        admin_email=None,
        admin_password=None,
        frontend_dir=str(tmp_path),
        migrations_dir=str(tmp_path),
        require_remote=None,
    )

    config = build_config(args)

    assert config.admin_email == "owner@lugano.com.br"
    assert config.require_remote is False


def test_build_config_parses_require_remote(monkeypatch, tmp_path):
    monkeypatch.setenv("FINAL_SECURITY_REQUIRE_REMOTE", "true")
    args = argparse.Namespace(
        admin_api_key_enabled="false",
        allowed_origins="https://app.lugano.com.br",
        supabase_url="https://lugano.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        api_base_url=None,
        admin_email=None,
        admin_password=None,
        frontend_dir=str(tmp_path),
        migrations_dir=str(tmp_path),
        require_remote=None,
    )

    config = build_config(args)

    assert config.require_remote is True
