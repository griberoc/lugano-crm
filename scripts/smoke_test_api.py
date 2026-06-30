import argparse
import os
from pathlib import Path
from typing import Any

import httpx

from supabase import create_client

ROOT_DIR = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def print_step(name: str, data: Any) -> None:
    print(f"\n== {name}")
    print(data)


def ensure_test_data(access_token: str) -> dict[str, str]:
    supabase_url = require_env("SUPABASE_URL")
    service_key = require_env("SUPABASE_SERVICE_ROLE_KEY")
    admin = create_client(supabase_url, service_key)

    user_response = admin.auth.get_user(access_token)
    if not user_response.user:
        raise RuntimeError(
            "Token is valid syntactically, but no Supabase user was found."
        )

    user_id = user_response.user.id
    email = user_response.user.email

    admin.table("profiles").upsert(
        {
            "id": user_id,
            "email": email,
            "full_name": "Cliente Smoke Test",
            "phone": "11999999999",
        }
    ).execute()

    tier_response = (
        admin.table("loyalty_tiers")
        .select("id")
        .order("min_points")
        .limit(1)
        .execute()
    )
    if not tier_response.data:
        raise RuntimeError("No loyalty tiers found. Run 001_initial_schema.sql first.")

    account_response = (
        admin.table("loyalty_accounts")
        .select("id")
        .eq("profile_id", user_id)
        .limit(1)
        .execute()
    )
    if not account_response.data:
        admin.table("loyalty_accounts").insert(
            {
                "profile_id": user_id,
                "tier_id": tier_response.data[0]["id"],
                "total_points": 0,
                "available_points": 0,
            }
        ).execute()

    address_response = (
        admin.table("addresses")
        .select("id")
        .eq("profile_id", user_id)
        .eq("label", "Smoke Test")
        .limit(1)
        .execute()
    )
    if address_response.data:
        address_id = address_response.data[0]["id"]
    else:
        created_address = (
            admin.table("addresses")
            .insert(
                {
                    "profile_id": user_id,
                    "label": "Smoke Test",
                    "street": "Rua Lugano",
                    "number": "100",
                    "neighborhood": "Centro",
                    "city": "Gramado",
                    "zip_code": "95670000",
                    "is_default": True,
                }
            )
            .execute()
        )
        address_id = created_address.data[0]["id"]

    product_response = (
        admin.table("products")
        .select("id, name, price")
        .eq("available", True)
        .limit(1)
        .execute()
    )
    if not product_response.data:
        raise RuntimeError(
            "No available products found. Run 001_initial_schema.sql first."
        )

    return {
        "user_id": user_id,
        "address_id": address_id,
        "product_id": product_response.data[0]["id"],
        "product_name": product_response.data[0]["name"],
    }


def request_json(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    expected_status: int,
    **kwargs: Any,
) -> Any:
    response = client.request(method, path, **kwargs)
    try:
        body = response.json()
    except ValueError:
        body = response.text

    if response.status_code != expected_status:
        raise RuntimeError(
            f"{method} {path} expected {expected_status}, "
            f"got {response.status_code}: {body}"
        )
    return body


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test Lugano CRM API.")
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--token", default=os.getenv("TEST_ACCESS_TOKEN"))
    args = parser.parse_args()

    load_dotenv(ROOT_DIR / ".env")

    if not args.token:
        raise RuntimeError(
            "Provide a Supabase access token with --token or TEST_ACCESS_TOKEN."
        )

    seeded = ensure_test_data(args.token)
    print_step("Prepared Supabase data", seeded)

    headers = {"Authorization": f"Bearer {args.token}"}
    with httpx.Client(base_url=args.base_url, timeout=20) as client:
        health = request_json(client, "GET", "/health", expected_status=200)
        print_step("GET /health", health)

        loyalty = request_json(
            client,
            "GET",
            "/api/v1/loyalty/",
            expected_status=200,
            headers=headers,
        )
        print_step("GET /api/v1/loyalty/", loyalty)

        promotion = request_json(
            client,
            "POST",
            "/api/v1/promotions/validate",
            expected_status=200,
            headers=headers,
            json={"code": "LUGANO10", "order_subtotal": 5000},
        )
        print_step("POST /api/v1/promotions/validate", promotion)

        order = request_json(
            client,
            "POST",
            "/api/v1/orders/",
            expected_status=201,
            headers=headers,
            json={
                "address_id": seeded["address_id"],
                "payment_method": "pix",
                "items": [
                    {
                        "product_id": seeded["product_id"],
                        "quantity": 1,
                        "customization": "Smoke test",
                    }
                ],
                "notes": "Pedido criado pelo smoke test",
            },
        )
        print_step("POST /api/v1/orders/", order)

        order_id = order["id"]
        fetched_order = request_json(
            client,
            "GET",
            f"/api/v1/orders/{order_id}",
            expected_status=200,
            headers=headers,
        )
        print_step(f"GET /api/v1/orders/{order_id}", fetched_order)

        orders = request_json(
            client,
            "GET",
            "/api/v1/orders/",
            expected_status=200,
            headers=headers,
        )
        print_step("GET /api/v1/orders/", {"count": len(orders)})

        cancelled = request_json(
            client,
            "POST",
            f"/api/v1/orders/{order_id}/cancel",
            expected_status=200,
            headers=headers,
        )
        print_step(f"POST /api/v1/orders/{order_id}/cancel", cancelled)

    print("\nSmoke test finished successfully.")


if __name__ == "__main__":
    main()
