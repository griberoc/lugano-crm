import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]

REQUIRED_MIGRATIONS = (
    "001_initial_schema.sql",
    "002_rls_policies.sql",
    "003_profile_auth_metadata.sql",
    "004_admin_roles.sql",
    "005_customer_preferences.sql",
    "006_security_hardening.sql",
    "007_notifications.sql",
    "008_audit_logs.sql",
    "009_operational_settings.sql",
    "010_data_retention.sql",
    "011_payments.sql",
    "012_sensitive_rls_lockdown.sql",
)

REQUIRED_TABLES = (
    "profiles",
    "addresses",
    "products",
    "orders",
    "order_items",
    "loyalty_tiers",
    "loyalty_accounts",
    "loyalty_transactions",
    "promotions",
    "promotion_usages",
    "admin_users",
    "notification_events",
    "audit_logs",
)

LOCAL_HOSTS = {"localhost", "0.0.0.0", "127.0.0.1", "::1"}
PLACEHOLDER_MARKERS = (
    "your-",
    "seu-",
    "sua-",
    "example.",
    "example-",
    "change-this",
    "...",
)


class SecurityReviewError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewResult:
    status: str
    name: str
    detail: str


@dataclass(frozen=True)
class SecurityReviewConfig:
    admin_api_key_enabled: str | None
    allowed_origins: str | None
    supabase_url: str | None
    supabase_anon_key: str | None
    supabase_service_role_key: str | None
    api_base_url: str | None
    admin_email: str | None
    admin_password: str | None
    frontend_dir: Path
    migrations_dir: Path
    require_remote: bool = False


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


def env_or_arg(value: str | None, *env_names: str) -> str | None:
    if value:
        return value
    for env_name in env_names:
        result = os.getenv(env_name)
        if result:
            return result
    return None


def parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y", "on"}:
        return True
    if normalized in {"false", "0", "no", "n", "off"}:
        return False
    return None


def parse_bool_env(value: str | None, *, default: bool = False) -> bool:
    parsed = parse_bool(value)
    return default if parsed is None else parsed


def is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    lower_value = value.lower()
    return any(marker in lower_value for marker in PLACEHOLDER_MARKERS)


def parse_origins(value: str | None) -> list[str]:
    if not value:
        return []
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def validate_origin(origin: str) -> str | None:
    if origin == "*":
        return "wildcard nao e permitido"

    parsed = urlparse(origin)
    if parsed.scheme != "https":
        return "origem deve usar HTTPS"

    hostname = parsed.hostname
    if not hostname:
        return "origem sem hostname valido"

    lowered = hostname.lower()
    if lowered in LOCAL_HOSTS or lowered.startswith("127."):
        return "localhost/IP local nao e dominio real de producao"

    if lowered.endswith(".local") or lowered.endswith(".test"):
        return "dominio .local/.test nao e dominio real de producao"

    if is_placeholder(origin):
        return "origem parece placeholder, nao dominio real"

    return None


def add_result(
    results: list[ReviewResult],
    status: str,
    name: str,
    detail: str,
) -> None:
    results.append(ReviewResult(status=status, name=name, detail=detail))


def check_admin_api_key_disabled(
    config: SecurityReviewConfig,
    results: list[ReviewResult],
) -> None:
    parsed = parse_bool(config.admin_api_key_enabled)
    if parsed is False:
        add_result(results, "ok", "ADMIN_API_KEY_ENABLED", "fallback tecnico desligado")
        return
    if parsed is True:
        add_result(
            results,
            "fail",
            "ADMIN_API_KEY_ENABLED",
            "deve ser false em producao",
        )
        return
    add_result(
        results,
        "fail",
        "ADMIN_API_KEY_ENABLED",
        "variavel ausente ou invalida",
    )


def check_allowed_origins(
    config: SecurityReviewConfig,
    results: list[ReviewResult],
) -> None:
    origins = parse_origins(config.allowed_origins)
    if not origins:
        add_result(results, "fail", "ALLOWED_ORIGINS", "nenhuma origem configurada")
        return

    errors = []
    for origin in origins:
        error = validate_origin(origin)
        if error:
            errors.append(f"{origin}: {error}")

    if errors:
        add_result(results, "fail", "ALLOWED_ORIGINS", "; ".join(errors))
        return

    add_result(
        results,
        "ok",
        "ALLOWED_ORIGINS",
        f"{len(origins)} dominio(s) real(is) usando HTTPS",
    )


def check_supabase_keys(
    config: SecurityReviewConfig,
    results: list[ReviewResult],
) -> None:
    missing = []
    if not config.supabase_anon_key:
        missing.append("SUPABASE_ANON_KEY")
    if not config.supabase_service_role_key:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")

    if missing:
        add_result(results, "fail", "Supabase keys", f"ausente: {', '.join(missing)}")
        return

    if config.supabase_anon_key == config.supabase_service_role_key:
        add_result(
            results,
            "fail",
            "Supabase keys",
            "anon key e service role key nao podem ser iguais",
        )
        return

    if is_placeholder(config.supabase_anon_key) or is_placeholder(
        config.supabase_service_role_key
    ):
        add_result(
            results,
            "warn",
            "Supabase keys",
            "uma das chaves parece placeholder; confirme no ambiente real",
        )
        return

    add_result(results, "ok", "Supabase keys", "anon e service role existem e diferem")


def frontend_files(frontend_dir: Path) -> list[Path]:
    if not frontend_dir.exists():
        return []
    allowed_suffixes = {".html", ".js", ".css", ".json"}
    return [
        path
        for path in frontend_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed_suffixes
    ]


def check_frontend_secret_exposure(
    config: SecurityReviewConfig,
    results: list[ReviewResult],
) -> None:
    files = frontend_files(config.frontend_dir)
    if not files:
        add_result(results, "fail", "Frontend secrets", "pasta frontend nao encontrada")
        return

    bad_matches: list[str] = []
    service_key = config.supabase_service_role_key or ""
    should_scan_exact_key = len(service_key) >= 20 and not is_placeholder(service_key)

    for path in files:
        content = path.read_text(encoding="utf-8", errors="ignore")
        lowered = content.lower()
        relative = path.relative_to(ROOT_DIR)
        if "supabase_service_role_key" in lowered or "service_role" in lowered:
            bad_matches.append(str(relative))
            continue
        if should_scan_exact_key and service_key in content:
            bad_matches.append(str(relative))

    if bad_matches:
        add_result(
            results,
            "fail",
            "Frontend secrets",
            "service role encontrada no frontend: " + ", ".join(bad_matches),
        )
        return

    add_result(
        results,
        "ok",
        "Frontend secrets",
        "frontend nao contem service role; use somente anon key publica",
    )


def check_local_migration_files(
    config: SecurityReviewConfig,
    results: list[ReviewResult],
) -> None:
    missing = [
        name
        for name in REQUIRED_MIGRATIONS
        if not (config.migrations_dir / name).exists()
    ]
    if missing:
        add_result(
            results,
            "fail",
            "Migration files 001-012",
            "arquivos ausentes: " + ", ".join(missing),
        )
        return

    add_result(results, "ok", "Migration files 001-012", "arquivos locais presentes")


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


def anon_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


def remote_available(config: SecurityReviewConfig) -> bool:
    return bool(
        config.supabase_url
        and config.supabase_anon_key
        and config.supabase_service_role_key
        and not is_placeholder(config.supabase_url)
        and not is_placeholder(config.supabase_anon_key)
        and not is_placeholder(config.supabase_service_role_key)
    )


def check_response_ok(
    response: httpx.Response,
    *,
    label: str,
) -> str | None:
    if response.status_code < 400:
        return None
    return f"{label} retornou {response.status_code}: {parse_body(response)}"


def check_remote_migrations(
    supabase: httpx.Client,
    config: SecurityReviewConfig,
    results: list[ReviewResult],
) -> None:
    if not remote_available(config):
        status = "fail" if config.require_remote else "warn"
        add_result(
            results,
            status,
            "Migrations remotas 001-012",
            "puladas: configure SUPABASE_URL, anon e service role reais",
        )
        return

    assert config.supabase_service_role_key
    errors = []
    for table in REQUIRED_TABLES:
        response = supabase.get(
            f"/rest/v1/{table}",
            headers=service_headers(config.supabase_service_role_key),
            params={"select": "id", "limit": "0"},
        )
        error = check_response_ok(response, label=table)
        if error:
            errors.append(error)

    profile_preferences = supabase.get(
        "/rest/v1/profiles",
        headers=service_headers(config.supabase_service_role_key),
        params={"select": "preferences", "limit": "0"},
    )
    error = check_response_ok(profile_preferences, label="profiles.preferences")
    if error:
        errors.append(error)

    if errors:
        add_result(
            results,
            "fail",
            "Migrations remotas 001-012",
            "; ".join(errors),
        )
        return

    add_result(
        results,
        "ok",
        "Migrations remotas 001-012",
        "tabelas/colunas esperadas respondem no Supabase",
    )


def check_remote_rls(
    supabase: httpx.Client,
    config: SecurityReviewConfig,
    results: list[ReviewResult],
) -> None:
    if not remote_available(config):
        status = "fail" if config.require_remote else "warn"
        add_result(
            results,
            status,
            "RLS basico",
            "pulado: configure SUPABASE_URL, anon e service role reais",
        )
        return

    assert config.supabase_anon_key
    headers = anon_headers(config.supabase_anon_key)
    products = supabase.get(
        "/rest/v1/products",
        headers=headers,
        params={"select": "id", "limit": "1"},
    )
    if products.status_code >= 400:
        add_result(
            results,
            "fail",
            "RLS basico",
            f"anon deveria ler products, recebeu {products.status_code}",
        )
        return

    denied_errors = []
    for table in ("orders", "audit_logs"):
        response = supabase.get(
            f"/rest/v1/{table}",
            headers=headers,
            params={"select": "id", "limit": "1"},
        )
        if response.status_code < 400:
            denied_errors.append(f"anon conseguiu ler {table}")

    if denied_errors:
        add_result(results, "fail", "RLS basico", "; ".join(denied_errors))
        return

    add_result(
        results,
        "ok",
        "RLS basico",
        "anon le products e nao le orders/audit_logs",
    )


def check_owner_via_service_role(
    supabase: httpx.Client,
    config: SecurityReviewConfig,
) -> str | None:
    if not config.admin_email:
        return "owner email ausente"

    assert config.supabase_service_role_key
    profiles = supabase.get(
        "/rest/v1/profiles",
        headers=service_headers(config.supabase_service_role_key),
        params={
            "select": "id,email",
            "email": f"eq.{config.admin_email}",
            "limit": "1",
        },
    )
    if profiles.status_code >= 400:
        return f"profiles retornou {profiles.status_code}: {parse_body(profiles)}"

    profile_rows = parse_body(profiles)
    if not profile_rows:
        return "perfil do owner nao encontrado em public.profiles"

    profile_id = profile_rows[0]["id"]
    admin_users = supabase.get(
        "/rest/v1/admin_users",
        headers=service_headers(config.supabase_service_role_key),
        params={
            "select": "profile_id,role,active",
            "profile_id": f"eq.{profile_id}",
            "limit": "1",
        },
    )
    if admin_users.status_code >= 400:
        body = parse_body(admin_users)
        return f"admin_users retornou {admin_users.status_code}: {body}"

    admin_rows = parse_body(admin_users)
    if not admin_rows:
        return "registro do owner nao encontrado em public.admin_users"

    admin = admin_rows[0]
    if admin.get("role") != "owner" or admin.get("active") is not True:
        return f"owner invalido: role={admin.get('role')} active={admin.get('active')}"

    return None


def check_owner_via_admin_login(
    api: httpx.Client,
    config: SecurityReviewConfig,
) -> str | None:
    if not config.api_base_url or not config.admin_email or not config.admin_password:
        return None

    response = api.post(
        "/api/v1/admin/login",
        json={"email": config.admin_email, "password": config.admin_password},
    )
    if response.status_code != 200:
        return f"login admin retornou {response.status_code}: {parse_body(response)}"

    body = parse_body(response)
    admin = body.get("admin") or {}
    if admin.get("role") != "owner":
        return f"login admin nao retornou owner: {admin.get('role')}"

    return None


def check_owner_admin(
    api: httpx.Client,
    supabase: httpx.Client,
    config: SecurityReviewConfig,
    results: list[ReviewResult],
) -> None:
    if not remote_available(config):
        status = "fail" if config.require_remote else "warn"
        add_result(
            results,
            status,
            "Owner admin",
            "pulado: configure SUPABASE_URL, anon e service role reais",
        )
        return

    service_error = check_owner_via_service_role(supabase, config)
    login_error = check_owner_via_admin_login(api, config)

    if service_error:
        add_result(results, "fail", "Owner admin", service_error)
        return

    if login_error:
        add_result(results, "fail", "Owner admin login", login_error)
        return

    detail = "owner ativo encontrado em public.admin_users"
    if config.api_base_url and config.admin_password:
        detail += " e login administrativo validado"
    else:
        detail += "; login pulado por falta de API_BASE_URL/PREDEPLOY_ADMIN_PASSWORD"

    add_result(results, "ok", "Owner admin", detail)


def run_review_with_clients(
    config: SecurityReviewConfig,
    *,
    api: httpx.Client,
    supabase: httpx.Client,
) -> list[ReviewResult]:
    results: list[ReviewResult] = []
    check_admin_api_key_disabled(config, results)
    check_allowed_origins(config, results)
    check_supabase_keys(config, results)
    check_frontend_secret_exposure(config, results)
    check_local_migration_files(config, results)
    check_remote_migrations(supabase, config, results)
    check_remote_rls(supabase, config, results)
    check_owner_admin(api, supabase, config, results)
    return results


def run_review(config: SecurityReviewConfig) -> list[ReviewResult]:
    with (
        httpx.Client(
            base_url=(config.api_base_url or "https://api.local").rstrip("/"),
            timeout=30,
        ) as api,
        httpx.Client(
            base_url=(config.supabase_url or "https://supabase.local").rstrip("/"),
            timeout=30,
        ) as supabase,
    ):
        return run_review_with_clients(config, api=api, supabase=supabase)


def print_results(results: list[ReviewResult]) -> None:
    labels = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}
    for result in results:
        print(f"[{labels[result.status]}] {result.name}: {result.detail}")


def has_failures(results: list[ReviewResult]) -> bool:
    return any(result.status == "fail" for result in results)


def build_config(args: argparse.Namespace) -> SecurityReviewConfig:
    return SecurityReviewConfig(
        admin_api_key_enabled=env_or_arg(
            args.admin_api_key_enabled,
            "ADMIN_API_KEY_ENABLED",
        ),
        allowed_origins=env_or_arg(args.allowed_origins, "ALLOWED_ORIGINS"),
        supabase_url=env_or_arg(args.supabase_url, "SUPABASE_URL"),
        supabase_anon_key=env_or_arg(args.supabase_anon_key, "SUPABASE_ANON_KEY"),
        supabase_service_role_key=env_or_arg(
            args.supabase_service_role_key,
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
        api_base_url=env_or_arg(args.api_base_url, "API_BASE_URL"),
        admin_email=env_or_arg(
            args.admin_email,
            "FINAL_SECURITY_OWNER_EMAIL",
            "PREDEPLOY_ADMIN_EMAIL",
            "SEED_OWNER_EMAIL",
        ),
        admin_password=env_or_arg(
            args.admin_password,
            "FINAL_SECURITY_OWNER_PASSWORD",
            "PREDEPLOY_ADMIN_PASSWORD",
            "SEED_OWNER_PASSWORD",
        ),
        frontend_dir=Path(args.frontend_dir).resolve(),
        migrations_dir=Path(args.migrations_dir).resolve(),
        require_remote=parse_bool_env(
            env_or_arg(args.require_remote, "FINAL_SECURITY_REQUIRE_REMOTE"),
            default=False,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Revisao final de seguranca do Lugano CRM.",
    )
    parser.add_argument("--env-file", default=".env.production")
    parser.add_argument("--admin-api-key-enabled")
    parser.add_argument("--allowed-origins")
    parser.add_argument("--supabase-url")
    parser.add_argument("--supabase-anon-key")
    parser.add_argument("--supabase-service-role-key")
    parser.add_argument("--api-base-url")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password")
    parser.add_argument("--frontend-dir", default=str(ROOT_DIR / "frontend"))
    parser.add_argument(
        "--migrations-dir",
        default=str(ROOT_DIR / "supabase" / "migrations"),
    )
    parser.add_argument(
        "--require-remote",
        choices=("true", "false"),
        help="Se true, checks remotos pulados viram falha.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT_DIR / ".env")
    if args.env_file:
        load_dotenv((ROOT_DIR / args.env_file).resolve(), override=True)

    try:
        results = run_review(build_config(args))
    except SecurityReviewError as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"\n[FAIL] HTTP error: {exc}", file=sys.stderr)
        return 1

    print_results(results)
    if has_failures(results):
        print("\nFinal security review failed.", file=sys.stderr)
        return 1

    print("\nFinal security review finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
