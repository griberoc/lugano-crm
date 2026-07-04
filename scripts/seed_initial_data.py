import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SEED_FILE = ROOT_DIR / "supabase" / "seeds" / "initial_data.json"


class SeedError(RuntimeError):
    pass


@dataclass(frozen=True)
class SeedConfig:
    supabase_url: str
    supabase_service_role_key: str
    owner_email: str
    owner_password: str | None = None
    owner_full_name: str = "Owner Lugano"
    seed_file: Path = DEFAULT_SEED_FILE
    dry_run: bool = False
    disable_missing_products: bool = False


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
        raise SeedError(f"Missing {env_name}. Provide CLI option or environment value.")
    return result


def service_headers(key: str, *, prefer: str | None = None) -> dict[str, str]:
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


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
        raise SeedError(
            f"{method} {path} expected {sorted(expected)}, "
            f"got {response.status_code}: {body}"
        )
    return body


def print_step(name: str, data: Any | None = None) -> None:
    print(f"[OK] {name}")
    if data is not None:
        print(f"     {data}")


def load_seed_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SeedError(f"Seed file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("loyalty_tiers", "products", "promotions", "operational_settings"):
        if key not in data or not isinstance(data[key], list):
            raise SeedError(f"Seed file must include list: {key}")
    return data


def find_record(
    client: httpx.Client,
    config: SeedConfig,
    table: str,
    field: str,
    value: str,
    *,
    select: str = "*",
) -> dict[str, Any] | None:
    records = request_json(
        client,
        "GET",
        f"/rest/v1/{table}",
        expected_status=200,
        headers=service_headers(config.supabase_service_role_key),
        params={"select": select, field: f"eq.{value}", "limit": "1"},
    )
    return records[0] if records else None


def upsert_by_field(
    client: httpx.Client,
    config: SeedConfig,
    table: str,
    field: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    existing = find_record(
        client,
        config,
        table,
        field,
        str(payload[field]),
        select="*",
    )
    headers = service_headers(
        config.supabase_service_role_key,
        prefer="return=representation",
    )

    if existing:
        response = request_json(
            client,
            "PATCH",
            f"/rest/v1/{table}",
            expected_status=200,
            headers=headers,
            params={field: f"eq.{payload[field]}"},
            json=payload,
        )
        return response[0] if response else {**existing, **payload}

    response = request_json(
        client,
        "POST",
        f"/rest/v1/{table}",
        expected_status=201,
        headers=headers,
        json=payload,
    )
    return response[0]


def list_auth_users(client: httpx.Client, config: SeedConfig) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = []
    page = 1
    while page <= 10:
        response = request_json(
            client,
            "GET",
            "/auth/v1/admin/users",
            expected_status=200,
            headers=service_headers(config.supabase_service_role_key),
            params={"page": str(page), "per_page": "100"},
        )
        page_users = response.get(
            "users",
            response if isinstance(response, list) else [],
        )
        users.extend(page_users)
        if len(page_users) < 100:
            break
        page += 1
    return users


def find_auth_user_by_email(
    client: httpx.Client,
    config: SeedConfig,
    email: str,
) -> dict[str, Any] | None:
    normalized_email = email.strip().lower()
    for user in list_auth_users(client, config):
        if str(user.get("email", "")).lower() == normalized_email:
            return user
    return None


def create_auth_user(
    client: httpx.Client,
    config: SeedConfig,
) -> dict[str, Any]:
    if not config.owner_password:
        raise SeedError(
            "Owner user does not exist. Provide SEED_OWNER_PASSWORD to create it."
        )
    return request_json(
        client,
        "POST",
        "/auth/v1/admin/users",
        expected_status={200, 201},
        headers=service_headers(config.supabase_service_role_key),
        json={
            "email": config.owner_email,
            "password": config.owner_password,
            "email_confirm": True,
            "user_metadata": {"full_name": config.owner_full_name},
        },
    )


def ensure_owner_user(client: httpx.Client, config: SeedConfig) -> dict[str, Any]:
    user = find_auth_user_by_email(client, config, config.owner_email)
    if user:
        print_step("owner auth user encontrado", {"email": user.get("email")})
        return user

    user = create_auth_user(client, config)
    print_step("owner auth user criado", {"email": user.get("email")})
    return user


def ensure_owner_profile_and_role(
    client: httpx.Client,
    config: SeedConfig,
    user: dict[str, Any],
) -> None:
    user_id = user["id"]
    upsert_headers = service_headers(
        config.supabase_service_role_key,
        prefer="resolution=merge-duplicates,return=representation",
    )
    request_json(
        client,
        "POST",
        "/rest/v1/profiles?on_conflict=id",
        expected_status={200, 201},
        headers=upsert_headers,
        json={
            "id": user_id,
            "email": user.get("email") or config.owner_email,
            "full_name": config.owner_full_name,
        },
    )
    request_json(
        client,
        "POST",
        "/rest/v1/admin_users?on_conflict=profile_id",
        expected_status={200, 201},
        headers=upsert_headers,
        json={"profile_id": user_id, "role": "owner", "active": True},
    )
    print_step("owner promovido", {"profile_id": user_id, "role": "owner"})


def seed_collection(
    client: httpx.Client,
    config: SeedConfig,
    table: str,
    field: str,
    items: list[dict[str, Any]],
) -> None:
    for item in items:
        upsert_by_field(client, config, table, field, item)
    print_step(f"{table} seed", {"count": len(items)})


def disable_products_not_in_seed(
    client: httpx.Client,
    config: SeedConfig,
    products: list[dict[str, Any]],
) -> None:
    seed_names = {str(item["name"]) for item in products}
    existing_products = request_json(
        client,
        "GET",
        "/rest/v1/products",
        expected_status=200,
        headers=service_headers(config.supabase_service_role_key),
        params={"select": "name,available"},
    )
    products_to_disable = [
        product
        for product in existing_products
        if product.get("name") not in seed_names and product.get("available") is not False
    ]
    headers = service_headers(
        config.supabase_service_role_key,
        prefer="return=minimal",
    )

    for product in products_to_disable:
        request_json(
            client,
            "PATCH",
            "/rest/v1/products",
            expected_status={200, 204},
            headers=headers,
            params={"name": f"eq.{product['name']}"},
            json={"available": False},
        )

    print_step("products fora do seed desativados", {"count": len(products_to_disable)})


def seed_operational_settings(
    client: httpx.Client,
    config: SeedConfig,
    items: list[dict[str, Any]],
) -> None:
    for item in items:
        payload = {
            "key": item["key"],
            "value": item["value"],
            "description": item.get("description"),
        }
        upsert_by_field(client, config, "operational_settings", "key", payload)
    print_step("operational_settings seed", {"count": len(items)})


def run_seed(config: SeedConfig) -> None:
    seed_data = load_seed_file(config.seed_file)
    if config.dry_run:
        print_step(
            "dry-run seed",
            {
                "loyalty_tiers": len(seed_data["loyalty_tiers"]),
                "products": len(seed_data["products"]),
                "promotions": len(seed_data["promotions"]),
                "operational_settings": len(seed_data["operational_settings"]),
                "owner_email": config.owner_email,
                "disable_missing_products": config.disable_missing_products,
            },
        )
        return

    with httpx.Client(base_url=config.supabase_url.rstrip("/"), timeout=30) as client:
        seed_collection(
            client,
            config,
            "loyalty_tiers",
            "name",
            seed_data["loyalty_tiers"],
        )
        seed_collection(client, config, "products", "name", seed_data["products"])
        if config.disable_missing_products:
            disable_products_not_in_seed(client, config, seed_data["products"])
        seed_collection(client, config, "promotions", "code", seed_data["promotions"])
        seed_operational_settings(
            client,
            config,
            seed_data["operational_settings"],
        )
        owner = ensure_owner_user(client, config)
        ensure_owner_profile_and_role(client, config, owner)


def build_config(args: argparse.Namespace) -> SeedConfig:
    return SeedConfig(
        supabase_url=env_or_arg(args.supabase_url, "SUPABASE_URL"),
        supabase_service_role_key=env_or_arg(
            args.supabase_service_role_key,
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
        owner_email=env_or_arg(args.owner_email, "SEED_OWNER_EMAIL"),
        owner_password=env_or_arg(
            args.owner_password,
            "SEED_OWNER_PASSWORD",
            required=False,
        ),
        owner_full_name=env_or_arg(
            args.owner_full_name,
            "SEED_OWNER_FULL_NAME",
            required=False,
        ) or "Owner Lugano",
        seed_file=Path(args.seed_file).resolve(),
        dry_run=args.dry_run,
        disable_missing_products=args.disable_missing_products,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed inicial de staging/producao do Lugano CRM.",
    )
    parser.add_argument("--env-file", default=".env.staging")
    parser.add_argument("--supabase-url")
    parser.add_argument("--supabase-service-role-key")
    parser.add_argument("--owner-email")
    parser.add_argument("--owner-password")
    parser.add_argument("--owner-full-name")
    parser.add_argument("--seed-file", default=str(DEFAULT_SEED_FILE))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--disable-missing-products",
        action="store_true",
        help="Marca como indisponiveis os produtos que nao aparecem no seed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT_DIR / ".env")
    if args.env_file:
        load_dotenv((ROOT_DIR / args.env_file).resolve(), override=True)

    try:
        run_seed(build_config(args))
    except SeedError as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"\n[FAIL] HTTP error: {exc}", file=sys.stderr)
        return 1

    print("\nInitial seed finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
