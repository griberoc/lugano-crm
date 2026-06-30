from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # App
    app_env: Literal["development", "test", "staging", "production"] = "development"
    secret_key: str
    admin_api_key: str = "dev-admin-key-change-me"
    admin_api_key_enabled: bool = True
    allowed_origins: str = "http://localhost:3000"
    allowed_methods: str = "GET,POST,PATCH,DELETE,OPTIONS"
    allowed_headers: str = "Authorization,Content-Type,X-Admin-Key"
    log_level: str = "INFO"

    # Rate limit
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_exempt_paths: str = "/health,/health/ready,/docs,/redoc,/openapi.json"
    rate_limit_trust_proxy_headers: bool = False

    # Delivery
    delivery_base_fee: int = 500         # centavos
    delivery_free_threshold: int = 5000  # centavos

    # Pagamentos
    payment_provider: Literal["manual", "pix_static", "mercado_pago"] = "manual"
    pix_key: str | None = None
    pix_merchant_name: str = "Lugano"
    pix_merchant_city: str = "Gramado"
    pix_txid_prefix: str = "LUG"
    pix_expires_minutes: int = 30
    mercado_pago_access_token: str | None = None
    mercado_pago_notification_url: str | None = None
    mercado_pago_webhook_secret: str | None = None
    mercado_pago_timeout_seconds: float = 10.0

    # Fidelidade
    points_per_real: int = 10

    # Notificacoes
    notifications_enabled: bool = True
    notification_email_enabled: bool = True
    notification_whatsapp_enabled: bool = True
    notification_email_webhook_url: str | None = None
    notification_email_webhook_token: str | None = None
    notification_whatsapp_webhook_url: str | None = None
    notification_whatsapp_webhook_token: str | None = None
    notification_webhook_timeout_seconds: float = 5.0

    # Monitoramento
    healthcheck_supabase_enabled: bool = True
    monitoring_alerts_enabled: bool = True
    monitoring_webhook_url: str | None = None
    monitoring_webhook_token: str | None = None
    monitoring_webhook_timeout_seconds: float = 5.0
    monitoring_service_name: str = "lugano-crm"

    @staticmethod
    def _csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def cors_allowed_origins(self) -> list[str]:
        origins = self._csv(self.allowed_origins)
        if self.app_env == "development":
            origins.extend(
                [
                    "http://localhost:5173",
                    "http://localhost:5174",
                    "http://localhost:5175",
                    "http://localhost:5176",
                    "http://127.0.0.1:5173",
                    "http://127.0.0.1:5174",
                    "http://127.0.0.1:5175",
                    "http://127.0.0.1:5176",
                ]
            )
        return list(dict.fromkeys(origins))

    @property
    def cors_allowed_methods(self) -> list[str]:
        return self._csv(self.allowed_methods)

    @property
    def cors_allowed_headers(self) -> list[str]:
        return self._csv(self.allowed_headers)

    @property
    def rate_limit_exempt_path_set(self) -> set[str]:
        return set(self._csv(self.rate_limit_exempt_paths))

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_deployed(self) -> bool:
        return self.app_env in {"staging", "production"}

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.supabase_anon_key == self.supabase_service_role_key:
            raise ValueError(
                "SUPABASE_ANON_KEY e SUPABASE_SERVICE_ROLE_KEY devem ser diferentes"
            )

        if not self.is_deployed:
            return self

        weak_secret_values = {
            "",
            "your-secret-key-min-32-chars",
            "change-this-admin-key",
            "dev-admin-key-change-me",
        }
        if len(self.secret_key) < 32 or self.secret_key in weak_secret_values:
            raise ValueError(
                "SECRET_KEY deve ter pelo menos 32 caracteres em staging/producao"
            )

        if self.admin_api_key_enabled and (
            len(self.admin_api_key) < 32 or self.admin_api_key in weak_secret_values
        ):
            raise ValueError(
                "ADMIN_API_KEY deve ser forte ou "
                "ADMIN_API_KEY_ENABLED=false em staging/producao"
            )

        origins = self._csv(self.allowed_origins)
        if not origins:
            raise ValueError("ALLOWED_ORIGINS deve ser definido em staging/producao")
        forbidden_origins = {"*", "http://localhost", "http://localhost:3000"}
        if any(
            origin in forbidden_origins
            or origin.startswith("http://127.")
            or origin.startswith("http://localhost:")
            for origin in origins
        ):
            raise ValueError(
                "ALLOWED_ORIGINS nao deve usar wildcard ou localhost "
                "em staging/producao"
            )

        if not self.supabase_url.startswith("https://"):
            raise ValueError("SUPABASE_URL deve usar HTTPS em staging/producao")

        return self


settings = Settings()
