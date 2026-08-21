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


def test_production_external_delivery_requires_credentials():
    with pytest.raises(ValidationError):
        make_settings(
            delivery_provider="external_api",
            delivery_api_base_url="",
            delivery_api_key="",
        )


def test_production_machine_delivery_requires_machine_credentials_and_origin():
    with pytest.raises(ValidationError):
        make_settings(
            delivery_provider="machine",
            delivery_api_base_url="https://api.taximachine.com.br/api/v2/integracao",
            delivery_api_key="machine-key",
            delivery_api_username="",
            delivery_api_password="",
            delivery_origin_address="",
            delivery_origin_neighborhood="",
        )


def test_production_accepts_complete_machine_delivery_config():
    settings = make_settings(
        delivery_provider="machine",
        delivery_api_base_url="https://api.taximachine.com.br/api/v2/integracao",
        delivery_api_key="machine-key",
        delivery_api_username="lugano",
        delivery_api_password="secret",
        delivery_origin_address="Avenida Colares Moreira, 10",
        delivery_origin_neighborhood="Jardim Renascenca",
        delivery_origin_city="Sao Luis",
        delivery_origin_state="ma",
    )

    assert settings.delivery_provider == "machine"
    assert settings.delivery_origin_state == "MA"


def test_empty_optional_machine_numeric_env_values_are_treated_as_none():
    settings = make_settings(
        app_env="development",
        delivery_origin_lat="",
        delivery_origin_lng="",
        delivery_machine_category_id="",
        delivery_machine_cancel_reason_id="",
    )

    assert settings.delivery_origin_lat is None
    assert settings.delivery_origin_lng is None
    assert settings.delivery_machine_category_id is None
    assert settings.delivery_machine_cancel_reason_id is None


def test_numeric_env_values_accept_inline_comments():
    settings = make_settings(
        app_env="development",
        delivery_base_fee="500        # em centavos",
        delivery_free_threshold="5000 # pedido acima de R$ 50,00",
        points_per_real="10           # 10 pontos por R$ 1,00",
        delivery_origin_lat="-2.505   # latitude da loja",
        delivery_machine_category_id="123 # categoria Machine",
    )

    assert settings.delivery_base_fee == 500
    assert settings.delivery_free_threshold == 5000
    assert settings.points_per_real == 10
    assert settings.delivery_origin_lat == -2.505
    assert settings.delivery_machine_category_id == 123


def test_production_mercado_pago_requires_access_token_and_notification_url():
    with pytest.raises(ValidationError):
        make_settings(
            payment_provider="mercado_pago",
            mercado_pago_access_token="",
            mercado_pago_notification_url="",
        )


def test_production_accepts_mercado_pago_config():
    settings = make_settings(
        payment_provider="mercado_pago",
        mercado_pago_access_token="APP_USR-valid-token",
        mercado_pago_notification_url=(
            "https://api.lugano.test/api/v1/payments/mercado-pago/webhook"
        ),
    )

    assert settings.payment_provider == "mercado_pago"
