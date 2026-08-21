import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]


class CheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckConfig:
    api_base_url: str
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    admin_email: str
    admin_password: str
    customer_email: str | None = None
    customer_password: str | None = None
    customer_access_token: str | None = None
    expected_env: str | None = "staging"
    keep_order: bool = False


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    user_id: str
    email: str | None = None
    role: str | None = None


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
        raise CheckError(
            f"Missing {env_name}. Provide CLI option or environment value."
        )
    return result


def print_step(name: str, data: Any | None = None) -> None:
    print(f"[OK] {name}")
    if data is not None:
        print(f"     {data}")


def print_warn(name: str, data: Any | None = None) -> None:
    print(f"[WARN] {name}")
    if data is not None:
        print(f"       {data}")


def parse_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    expected_status: int | set[int],
    **kwargs: Any,
) -> Any:
    response = client.request(method, path, **kwargs)
    body = parse_body(response)
    expected = (
        {expected_status} if isinstance(expected_status, int) else expected_status
    )
    if response.status_code not in expected:
        raise CheckError(
            f"{method} {path} expected {sorted(expected)}, "
            f"got {response.status_code}: {body}"
        )
    return body


def assert_denied(response: httpx.Response, label: str) -> None:
    if response.status_code < 400:
        raise CheckError(
            f"{label} should be denied by RLS/grants, got {response.status_code}: "
            f"{parse_body(response)}"
        )


def api_auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def supabase_headers(key: str, *, bearer: str | None = None) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {bearer or key}",
        "Content-Type": "application/json",
    }


def supabase_rest_headers(key: str, *, bearer: str | None = None) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {bearer or key}",
    }


def sign_in_supabase(
    supabase: httpx.Client,
    config: CheckConfig,
    email: str,
    password: str,
) -> AuthSession:
    response = request_json(
        supabase,
        "POST",
        "/auth/v1/token?grant_type=password",
        expected_status=200,
        headers=supabase_headers(config.supabase_anon_key),
        json={"email": email, "password": password},
    )
    user = response.get("user") or {}
    return AuthSession(
        access_token=response["access_token"],
        user_id=user.get("id"),
        email=user.get("email") or email,
    )


def check_health(api: httpx.Client, config: CheckConfig) -> None:
    health = request_json(api, "GET", "/health", expected_status=200)
    if config.expected_env and health.get("env") != config.expected_env:
        raise CheckError(
            f"/health env expected {config.expected_env!r}, got {health.get('env')!r}"
        )
    print_step("/health", health)


def login_admin(api: httpx.Client, config: CheckConfig) -> AuthSession:
    response = request_json(
        api,
        "POST",
        "/api/v1/admin/login",
        expected_status=200,
        json={"email": config.admin_email, "password": config.admin_password},
    )
    admin = response.get("admin") or {}
    if admin.get("role") != "owner":
        raise CheckError(
            "Pre-deploy audit check requires an owner admin. "
            f"Logged role: {admin.get('role')}"
        )
    user = response.get("user") or {}
    session = AuthSession(
        access_token=response["access_token"],
        user_id=admin.get("profile_id") or user.get("id"),
        email=admin.get("email") or user.get("email"),
        role=admin.get("role"),
    )
    print_step("login admin", {"email": session.email, "role": session.role})
    return session


def list_products(api: httpx.Client, admin: AuthSession) -> dict[str, Any]:
    products = request_json(
        api,
        "GET",
        "/api/v1/admin/products",
        expected_status=200,
        headers=api_auth_headers(admin.access_token),
    )
    available = [product for product in products if product.get("available")]
    if not available:
        raise CheckError(
            "No available product found. Run the production/staging seed first."
        )
    product = available[0]
    print_step(
        "listagem de produtos",
        {"count": len(products), "product": product["name"]},
    )
    return product


def get_customer_session(
    supabase: httpx.Client,
    config: CheckConfig,
) -> AuthSession:
    if config.customer_access_token:
        response = request_json(
            supabase,
            "GET",
            "/auth/v1/user",
            expected_status=200,
            headers=supabase_rest_headers(
                config.supabase_anon_key,
                bearer=config.customer_access_token,
            ),
        )
        return AuthSession(
            access_token=config.customer_access_token,
            user_id=response["id"],
            email=response.get("email"),
        )

    if not config.customer_email or not config.customer_password:
        raise CheckError(
            "Provide PREDEPLOY_CUSTOMER_ACCESS_TOKEN or "
            "PREDEPLOY_CUSTOMER_EMAIL/PREDEPLOY_CUSTOMER_PASSWORD."
        )
    session = sign_in_supabase(
        supabase,
        config,
        config.customer_email,
        config.customer_password,
    )
    print_step("login cliente", {"email": session.email})
    return session


def select_one(
    supabase: httpx.Client,
    config: CheckConfig,
    table: str,
    params: dict[str, str],
) -> dict[str, Any] | None:
    response = request_json(
        supabase,
        "GET",
        f"/rest/v1/{table}",
        expected_status=200,
        headers=supabase_rest_headers(config.supabase_service_role_key),
        params={**params, "limit": "1"},
    )
    return response[0] if response else None


def ensure_customer_data(
    supabase: httpx.Client,
    config: CheckConfig,
    customer: AuthSession,
) -> str:
    service_headers = supabase_headers(config.supabase_service_role_key)
    upsert_headers = {
        **service_headers,
        "Prefer": "resolution=merge-duplicates,return=representation",
    }
    request_json(
        supabase,
        "POST",
        "/rest/v1/profiles?on_conflict=id",
        expected_status={200, 201},
        headers=upsert_headers,
        json={
            "id": customer.user_id,
            "email": customer.email,
            "full_name": "[PREDEPLOY] Cliente Teste",
            "phone": "11999999999",
        },
    )

    tier = select_one(
        supabase,
        config,
        "loyalty_tiers",
        {"select": "id", "order": "min_points.asc"},
    )
    if not tier:
        raise CheckError("No loyalty tier found. Run migrations/seeds first.")

    account = select_one(
        supabase,
        config,
        "loyalty_accounts",
        {"select": "id", "profile_id": f"eq.{customer.user_id}"},
    )
    if not account:
        request_json(
            supabase,
            "POST",
            "/rest/v1/loyalty_accounts",
            expected_status=201,
            headers={**service_headers, "Prefer": "return=representation"},
            json={
                "profile_id": customer.user_id,
                "tier_id": tier["id"],
                "total_points": 0,
                "available_points": 0,
            },
        )

    address = select_one(
        supabase,
        config,
        "addresses",
        {
            "select": "id",
            "profile_id": f"eq.{customer.user_id}",
            "label": "eq.Pre-deploy",
        },
    )
    if address:
        print_step("dados do cliente preparados", {"address_id": address["id"]})
        return address["id"]

    created_address = request_json(
        supabase,
        "POST",
        "/rest/v1/addresses",
        expected_status=201,
        headers={**service_headers, "Prefer": "return=representation"},
        json={
            "profile_id": customer.user_id,
            "label": "Pre-deploy",
            "street": "Rua Lugano",
            "number": "100",
            "neighborhood": "Centro",
            "city": "Gramado",
            "zip_code": "95670000",
            "is_default": True,
        },
    )
    address_id = created_address[0]["id"]
    print_step("dados do cliente preparados", {"address_id": address_id})
    return address_id


def create_order(
    api: httpx.Client,
    customer: AuthSession,
    product: dict[str, Any],
    address_id: str,
) -> dict[str, Any]:
    order = request_json(
        api,
        "POST",
        "/api/v1/orders/",
        expected_status=201,
        headers=api_auth_headers(customer.access_token),
        json={
            "address_id": address_id,
            "payment_method": "pix",
            "items": [
                {
                    "product_id": product["id"],
                    "quantity": 1,
                    "customization": "Pre-deploy check",
                }
            ],
            "notes": "Pedido criado pelo checklist automatico de pre-deploy",
        },
    )
    print_step(
        "criacao de pedido",
        {"order_id": order["id"], "status": order["status"]},
    )
    return order


def read_order_admin(
    api: httpx.Client,
    admin: AuthSession,
    order_id: str,
) -> dict[str, Any]:
    order = request_json(
        api,
        "GET",
        f"/api/v1/admin/orders/{order_id}",
        expected_status=200,
        headers=api_auth_headers(admin.access_token),
    )
    if order.get("id") != order_id:
        raise CheckError(f"Admin order read returned unexpected id: {order.get('id')}")
    print_step("leitura do pedido no admin", {"order_id": order_id})
    return order


def generate_and_check_audit(
    api: httpx.Client,
    admin: AuthSession,
    order_id: str,
) -> None:
    updated = request_json(
        api,
        "PATCH",
        f"/api/v1/admin/orders/{order_id}",
        expected_status=200,
        headers=api_auth_headers(admin.access_token),
        json={"status": "confirmed"},
    )
    print_step(
        "alteracao administrativa",
        {"order_id": order_id, "status": updated["status"]},
    )

    logs = request_json(
        api,
        "GET",
        "/api/v1/admin/audit-logs?entity_type=order&page_size=20",
        expected_status=200,
        headers=api_auth_headers(admin.access_token),
    )
    matched = [
        log for log in logs
        if log.get("entity_id") == order_id and log.get("action") == "order.update"
    ]
    if not matched:
        raise CheckError(f"No order.update audit log found for order {order_id}.")
    print_step("auditoria gerada", {"audit_log_id": matched[0]["id"]})


def check_rls(
    supabase: httpx.Client,
    config: CheckConfig,
    customer: AuthSession,
    order_id: str,
) -> None:
    anon_headers = supabase_rest_headers(config.supabase_anon_key)
    customer_headers = supabase_rest_headers(
        config.supabase_anon_key,
        bearer=customer.access_token,
    )

    request_json(
        supabase,
        "GET",
        "/rest/v1/products",
        expected_status=200,
        headers=anon_headers,
        params={"select": "id", "limit": "1"},
    )

    anon_orders = supabase.get(
        "/rest/v1/orders",
        headers=anon_headers,
        params={"select": "id", "limit": "1"},
    )
    assert_denied(anon_orders, "Anonymous orders select")

    own_orders = request_json(
        supabase,
        "GET",
        "/rest/v1/orders",
        expected_status=200,
        headers=customer_headers,
        params={"select": "id,profile_id", "id": f"eq.{order_id}"},
    )
    if not own_orders or own_orders[0].get("profile_id") != customer.user_id:
        raise CheckError("Customer RLS did not return the created own order.")

    other_order = select_one(
        supabase,
        config,
        "orders",
        {
            "select": "id,profile_id",
            "profile_id": f"neq.{customer.user_id}",
        },
    )
    if not other_order:
        raise CheckError(
            "Customer isolation needs an order owned by another profile. "
            "Create the documented RLS fixture and run the check again."
        )
    other_orders = request_json(
        supabase,
        "GET",
        "/rest/v1/orders",
        expected_status=200,
        headers=customer_headers,
        params={"select": "id", "id": f"eq.{other_order['id']}"},
    )
    if other_orders:
        raise CheckError("Customer RLS exposed an order owned by another profile.")

    customer_audit = supabase.get(
        "/rest/v1/audit_logs",
        headers=customer_headers,
        params={"select": "id", "limit": "1"},
    )
    assert_denied(customer_audit, "Customer audit_logs select")
    print_step(
        "RLS basica",
        "products anon ok, orders anon denied, own order ok, other order hidden, "
        "audit denied",
    )


def cleanup_order(api: httpx.Client, customer: AuthSession, order_id: str) -> None:
    response = api.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers=api_auth_headers(customer.access_token),
    )
    if response.status_code == 200:
        print_step(
            "limpeza do pedido de teste",
            {"status": parse_body(response)["status"]},
        )
    else:
        print_warn("nao foi possivel cancelar o pedido de teste", parse_body(response))


def run_check(config: CheckConfig) -> None:
    with (
        httpx.Client(base_url=config.api_base_url.rstrip("/"), timeout=30) as api,
        httpx.Client(base_url=config.supabase_url.rstrip("/"), timeout=30) as supabase,
    ):
        check_health(api, config)
        admin = login_admin(api, config)
        product = list_products(api, admin)
        customer = get_customer_session(supabase, config)
        address_id = ensure_customer_data(supabase, config, customer)
        order = create_order(api, customer, product, address_id)
        order_id = order["id"]
        read_order_admin(api, admin, order_id)
        generate_and_check_audit(api, admin, order_id)
        check_rls(supabase, config, customer, order_id)
        if not config.keep_order:
            cleanup_order(api, customer, order_id)


def build_config(args: argparse.Namespace) -> CheckConfig:
    return CheckConfig(
        api_base_url=env_or_arg(args.api_base_url, "API_BASE_URL"),
        supabase_url=env_or_arg(args.supabase_url, "SUPABASE_URL"),
        supabase_anon_key=env_or_arg(args.supabase_anon_key, "SUPABASE_ANON_KEY"),
        supabase_service_role_key=env_or_arg(
            args.supabase_service_role_key,
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
        admin_email=env_or_arg(args.admin_email, "PREDEPLOY_ADMIN_EMAIL"),
        admin_password=env_or_arg(args.admin_password, "PREDEPLOY_ADMIN_PASSWORD"),
        customer_email=env_or_arg(
            args.customer_email,
            "PREDEPLOY_CUSTOMER_EMAIL",
            required=False,
        ),
        customer_password=env_or_arg(
            args.customer_password,
            "PREDEPLOY_CUSTOMER_PASSWORD",
            required=False,
        ),
        customer_access_token=env_or_arg(
            args.customer_access_token,
            "PREDEPLOY_CUSTOMER_ACCESS_TOKEN",
            required=False,
        ),
        expected_env=env_or_arg(
            args.expected_env,
            "PREDEPLOY_EXPECTED_ENV",
            required=False,
        ) or "staging",
        keep_order=args.keep_order,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Checklist automatico de pre-deploy do Lugano CRM.",
    )
    parser.add_argument("--env-file", default=".env.staging")
    parser.add_argument("--api-base-url")
    parser.add_argument("--supabase-url")
    parser.add_argument("--supabase-anon-key")
    parser.add_argument("--supabase-service-role-key")
    parser.add_argument("--admin-email")
    parser.add_argument("--admin-password")
    parser.add_argument("--customer-email")
    parser.add_argument("--customer-password")
    parser.add_argument("--customer-access-token")
    parser.add_argument("--expected-env")
    parser.add_argument("--keep-order", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT_DIR / ".env")
    if args.env_file:
        load_dotenv((ROOT_DIR / args.env_file).resolve(), override=True)

    try:
        config = build_config(args)
        run_check(config)
    except CheckError as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"\n[FAIL] HTTP error: {exc}", file=sys.stderr)
        return 1

    print("\nPre-deploy checklist finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
