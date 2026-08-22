from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e
ARTIFACTS = Path("test-results/e2e")


def json_response(route, payload, status=200):
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload),
    )


@pytest.fixture
def fake_platform(page):
    address = {
        "id": "address-e2e",
        "label": "Casa",
        "street": "Rua das Flores",
        "number": "120",
        "neighborhood": "Centro",
        "city": "Gramado",
        "zip_code": "95670-000",
        "complement": None,
        "is_default": True,
    }
    product = {
        "id": "product-e2e",
        "name": "Chocolate quente E2E",
        "description": "Fixture do fluxo critico",
        "category": "cafeteria",
        "price": 24.9,
        "available": True,
        "image_url": None,
    }
    order = {
        "id": "order-e2e-0001",
        "profile_id": "customer-e2e",
        "status": "pending",
        "payment_status": "pending",
        "payment_method": "pix",
        "payment_provider": "manual",
        "payment_instructions": {
            "title": "Pix Lugano",
            "description": "Use o codigo para pagar.",
            "status": "pending",
            "pix_copy_paste": "PIX-E2E-NOT-A-REAL-CREDENTIAL",
        },
        "subtotal": 24.9,
        "delivery_fee": 8.0,
        "discount": 2.49,
        "total": 30.41,
        "notes": None,
        "placed_at": "2026-08-22T12:00:00Z",
        "created_at": "2026-08-22T12:00:00Z",
        "delivered_at": None,
        "address": address,
        "customer": {
            "full_name": "Cliente E2E",
            "email": "cliente.e2e@example.test",
            "phone": "5551999999999",
        },
        "items": [
            {
                "product_id": product["id"],
                "quantity": 1,
                "unit_price": product["price"],
                "product": product,
            }
        ],
    }
    state = {"addresses": [], "orders": [], "order": order, "patches": 0}

    def handler(route):
        request = route.request
        parsed = urlparse(request.url)
        path = parsed.path.rstrip("/") or "/"
        method = request.method

        if "/auth/v1/token" in parsed.path:
            data = request.post_data_json
            if data.get("password") == "senha-incorreta":
                return json_response(route, {"message": "Credenciais invalidas"}, 400)
            return json_response(
                route,
                {
                    "access_token": "customer-e2e-token",
                    "refresh_token": "customer-e2e-refresh",
                    "expires_in": 3600,
                    "user": {"id": "customer-e2e", "email": data["email"]},
                },
            )

        if not path.startswith("/api/v1"):
            return route.continue_()

        if path == "/api/v1/catalog/products":
            return json_response(route, [product])
        if path == "/api/v1/orders/quote":
            return json_response(
                route,
                {
                    "subtotal_cents": 2490,
                    "delivery_fee_cents": 800,
                    "free_delivery_threshold_cents": 9000,
                    "amount_to_free_delivery_cents": 6510,
                },
            )
        if path == "/api/v1/me/addresses" and method == "POST":
            state["addresses"] = [address]
            return json_response(route, address, 201)
        if path == "/api/v1/me/addresses":
            return json_response(route, state["addresses"])
        if path == "/api/v1/promotions/validate":
            return json_response(
                route,
                {
                    "valid": True,
                    "code": "LUGANO10",
                    "description": "10% no pedido E2E",
                    "type": "percentage",
                    "discount": 249,
                },
            )
        if path == "/api/v1/orders" and method == "POST":
            if not state["orders"]:
                state["orders"].append(state["order"])
            return json_response(route, state["order"], 201)
        if path == "/api/v1/orders":
            return json_response(route, state["orders"])
        if path == f"/api/v1/orders/{order['id']}":
            return json_response(route, state["order"])
        if path == "/api/v1/admin/login":
            return json_response(
                route,
                {
                    "access_token": "admin-e2e-token",
                    "refresh_token": "admin-e2e-refresh",
                    "expires_in": 3600,
                    "user": {"id": "admin-e2e", "email": "admin@example.test"},
                    "admin": {
                        "profile_id": "admin-e2e",
                        "role": "owner",
                        "active": True,
                        "auth_method": "supabase",
                    },
                },
            )
        if path == "/api/v1/admin/orders":
            return json_response(route, state["orders"])
        if path == f"/api/v1/admin/orders/{order['id']}" and method == "PATCH":
            state["order"].update(request.post_data_json)
            state["patches"] += 1
            return json_response(route, state["order"])
        if path in {
            "/api/v1/admin/products",
            "/api/v1/admin/customers",
            "/api/v1/admin/promotions",
            "/api/v1/admin/users",
            "/api/v1/admin/audit-logs",
        }:
            return json_response(route, [])
        if path == "/api/v1/admin/reports":
            return json_response(
                route,
                {
                    "summary": {},
                    "sales_by_day": [],
                    "top_products": [],
                    "recurring_customers": [],
                    "coupon_usage": [],
                },
            )
        if path == "/api/v1/me":
            return json_response(
                route,
                {
                    "id": "customer-e2e",
                    "full_name": "Cliente E2E",
                    "email": "cliente.e2e@example.test",
                    "phone": None,
                    "preferences": {},
                },
            )
        if path == "/api/v1/loyalty":
            return json_response(
                route,
                {
                    "available_points": 30,
                    "total_points": 30,
                    "tier": {
                        "name": "Cacau",
                        "min_points": 0,
                        "cashback_rate": 5,
                        "benefits": {"boas_vindas": True},
                    },
                },
            )
        if path == "/api/v1/loyalty/transactions":
            return json_response(route, [])
        if path == "/api/v1/promotions/available":
            return json_response(route, [])

        return json_response(
            route,
            {"detail": f"Fixture E2E ausente para {method} {path}"},
            501,
        )

    page.route("**/*", handler)
    return state


@pytest.mark.parametrize(
    ("viewport", "artifact"),
    [
        ({"width": 1440, "height": 1000}, "critical-flow-desktop.png"),
        ({"width": 390, "height": 844}, "critical-flow-mobile.png"),
    ],
)
def test_customer_and_admin_critical_flow(
    page, frontend_url, fake_platform, viewport, artifact
):
    page.set_viewport_size(viewport)
    page.goto(f"{frontend_url}/landing/")
    expect(page.get_by_role("heading", name="Lugano Sao Luis")).to_be_visible()

    page.goto(f"{frontend_url}/client/#/delivery")
    delivery = page.frame_locator("#module-frame")
    delivery.get_by_role("button", name="Adicionar").click()
    expect(delivery.locator("#cart-count")).to_have_text("1 itens")
    delivery.get_by_role("button", name="Continuar").first.click()
    delivery.get_by_role("link", name="Ir para Acesso").click()

    access = page.frame_locator("#module-frame")
    access.locator("#login-form input[name=email]").fill("cliente.e2e@example.test")
    access.locator("#login-form input[name=password]").fill("senha-e2e")
    access.locator("#login-form").get_by_role("button", name="Entrar").click()
    page.wait_for_url("**/#/delivery")

    delivery = page.frame_locator("#module-frame")
    expect(delivery.locator("#cart-count")).to_have_text("1 itens")
    delivery.get_by_text("Novo endereco", exact=True).click()
    delivery.locator("#address-form input[name=street]").fill("Rua das Flores")
    delivery.locator("#address-form input[name=number]").fill("120")
    delivery.locator("#address-form input[name=neighborhood]").fill("Centro")
    delivery.locator("#address-form input[name=city]").fill("Gramado")
    delivery.locator("#address-form input[name=zip_code]").fill("95670-000")
    delivery.locator("#address-form").get_by_role(
        "button", name="Salvar endereco"
    ).click()
    expect(delivery.locator("#address-summary")).to_contain_text("Rua das Flores")
    delivery.locator("#promotion-code").fill("LUGANO10")
    delivery.locator("#validate-promotion").click()
    expect(delivery.locator("#promotion-summary")).to_contain_text("10%")
    delivery.locator("#checkout-button").click()
    delivery.locator("#confirm-order").click()
    expect(delivery.locator("#notice")).to_contain_text("Pedido enviado com sucesso")

    page.goto(f"{frontend_url}/admin/")
    page.locator("#admin-login-form input[name=email]").fill("admin@example.test")
    page.locator("#admin-login-form input[name=password]").fill("admin-e2e")
    page.locator("#admin-login-form").get_by_role(
        "button", name="Entrar no painel"
    ).click()
    page.get_by_role("button", name="Pedidos").click()
    page.get_by_role("button", name="Confirmado").first.click()
    expect(page.locator("#orders-queue")).to_contain_text("Confirmado")
    assert fake_platform["patches"] == 1

    page.goto(f"{frontend_url}/client/#/painel")
    panel = page.frame_locator("#module-frame")
    expect(panel.locator("#orders-list")).to_contain_text("Confirmado")
    expect(panel.locator("#loyalty-headline")).to_contain_text("30 pontos")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / artifact), full_page=True)
    assert len(fake_platform["orders"]) == 1


def test_login_error_is_clear(page, frontend_url, fake_platform):
    page.goto(f"{frontend_url}/auth/")
    page.locator("#login-form input[name=email]").fill("cliente.e2e@example.test")
    page.locator("#login-form input[name=password]").fill("senha-incorreta")
    page.locator("#login-form").get_by_role("button", name="Entrar").click()
    expect(page.locator("#notice")).to_contain_text(
        "Login falhou. Credenciais invalidas"
    )
