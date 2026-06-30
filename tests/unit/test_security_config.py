import pytest
from pydantic import ValidationError

from app.core.config import Settings


def make_settings(**overrides):
    data = {
        "supabase_url": "https://example.supabase.co",
        "supabase_anon_key": "anon-key",
        "supabase_service_role_key": "service-role-key",
        "app_env": "production",
        "secret_key": "s" * 32,
        "admin_api_key": "a" * 32,
        "allowed_origins": "https://app.lugano.test",
        **overrides,
    }
    return Settings(**data)


def test_production_rejects_weak_secret_key():
    with pytest.raises(ValidationError):
        make_settings(secret_key="short")


def test_production_rejects_localhost_cors_origin():
    with pytest.raises(ValidationError):
        make_settings(allowed_origins="http://localhost:5176")


def test_staging_uses_deployed_security_rules():
    with pytest.raises(ValidationError):
        make_settings(
            app_env="staging",
            secret_key="short",
            allowed_origins="http://localhost:5176",
        )


def test_production_allows_disabling_admin_api_key_fallback():
    settings = make_settings(
        admin_api_key="dev-admin-key-change-me",
        admin_api_key_enabled=False,
    )

    assert settings.admin_api_key_enabled is False


def test_rejects_equal_supabase_anon_and_service_role_keys():
    with pytest.raises(ValidationError):
        make_settings(
            app_env="development",
            supabase_anon_key="same-key",
            supabase_service_role_key="same-key",
        )
