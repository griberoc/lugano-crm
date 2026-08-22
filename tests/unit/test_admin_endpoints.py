from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.admin import AdminContext, require_admin
from app.core.config import settings
from app.main import app


def product_payload(**overrides):
    return {
        "name": "Chocolate Quente Teste",
        "description": "Bebida cremosa",
        "category": "chocolateria",
        "price": "19.90",
        "available": True,
        "image_url": None,
        **overrides,
    }


def use_admin_role(role: str):
    app.dependency_overrides[require_admin] = lambda: AdminContext(
        auth_method="test",
        role=role,
        profile_id="99999999-9999-9999-9999-999999999999",
        email=f"{role}@lugano.test",
    )


def clear_admin_role():
    app.dependency_overrides.pop(require_admin, None)


def test_admin_requires_valid_key():
    with pytest.raises(HTTPException) as exc_info:
        require_admin("wrong")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Admin key invalida"


def test_admin_key_can_be_disabled():
    previous_enabled = settings.admin_api_key_enabled
    previous_key = settings.admin_api_key
    settings.admin_api_key_enabled = False
    settings.admin_api_key = "test-admin-key"

    try:
        with pytest.raises(HTTPException) as exc_info:
            require_admin("test-admin-key")
    finally:
        settings.admin_api_key_enabled = previous_enabled
        settings.admin_api_key = previous_key

    assert exc_info.value.status_code == 403


def test_admin_me_accepts_technical_key(client, admin_headers):
    response = client.get("/api/v1/admin/me", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {
        "auth_method": "admin_key",
        "role": "owner",
        "profile_id": None,
        "email": None,
    }


def test_admin_creates_and_lists_products(client, admin_headers):
    create_response = client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json=product_payload(),
    )
    list_response = client.get("/api/v1/admin/products", headers=admin_headers)

    assert create_response.status_code == 201
    assert create_response.json()["name"] == "Chocolate Quente Teste"
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_admin_records_product_audit_log(client, admin_headers, fake_db):
    response = client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json=product_payload(name="Produto Auditavel"),
    )

    assert response.status_code == 201
    assert len(fake_db.tables["audit_logs"]) == 1
    audit_log = fake_db.tables["audit_logs"][0]
    assert audit_log["action"] == "product.create"
    assert audit_log["entity_type"] == "product"
    assert audit_log["entity_id"] == response.json()["id"]
    assert audit_log["actor_role"] == "owner"
    assert audit_log["auth_method"] == "admin_key"


def test_admin_updates_product(client, admin_headers):
    product = client.post(
        "/api/v1/admin/products",
        headers=admin_headers,
        json=product_payload(),
    ).json()

    response = client.patch(
        f"/api/v1/admin/products/{product['id']}",
        headers=admin_headers,
        json={"available": False, "price": "21.50"},
    )

    assert response.status_code == 200
    assert response.json()["available"] is False
    assert response.json()["price"] == "21.50"


def test_owner_lists_audit_logs(client, admin_headers, fake_db):
    fake_db.tables["audit_logs"].append(
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "actor_profile_id": None,
            "actor_email": None,
            "actor_role": "owner",
            "auth_method": "admin_key",
            "action": "product.update",
            "entity_type": "product",
            "entity_id": "22222222-2222-2222-2222-222222222222",
            "before_data": {"available": True},
            "after_data": {"available": False},
            "metadata": {"changed_fields": ["available"]},
            "created_at": datetime.now(UTC).isoformat(),
        }
    )

    response = client.get(
        "/api/v1/admin/audit-logs?entity_type=product",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()[0]["action"] == "product.update"


def test_staff_cannot_list_audit_logs(client):
    use_admin_role("staff")
    try:
        response = client.get("/api/v1/admin/audit-logs")
    finally:
        clear_admin_role()

    assert response.status_code == 403
    assert response.json()["detail"] == "Permissao administrativa insuficiente"


def test_staff_can_read_products(client, fake_db):
    fake_db.tables["products"].append(
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "Cappuccino Staff",
            "description": "Produto visivel para atendimento",
            "category": "cafeteria",
            "price": "16.90",
            "available": True,
            "image_url": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    use_admin_role("staff")
    try:
        response = client.get("/api/v1/admin/products")
    finally:
        clear_admin_role()

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Cappuccino Staff"


def test_staff_cannot_create_product(client):
    use_admin_role("staff")
    try:
        response = client.post(
            "/api/v1/admin/products",
            json=product_payload(),
        )
    finally:
        clear_admin_role()

    assert response.status_code == 403
    assert response.json()["detail"] == "Permissao administrativa insuficiente"


def test_admin_returns_404_for_missing_product(client, admin_headers):
    response = client.get(
        "/api/v1/admin/products/11111111-1111-1111-1111-111111111111",
        headers=admin_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Produto nao encontrado"


def test_admin_lists_and_updates_customers(client, admin_headers, fake_db):
    customer_id = "22222222-2222-2222-2222-222222222222"
    fake_db.tables["profiles"].append(
        {
            "id": customer_id,
            "full_name": "Cliente Antigo",
            "phone": "11999999999",
            "email": "cliente@lugano.test",
            "birth_date": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )

    list_response = client.get("/api/v1/admin/customers", headers=admin_headers)
    update_response = client.patch(
        f"/api/v1/admin/customers/{customer_id}",
        headers=admin_headers,
        json={"full_name": "Cliente Novo"},
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["full_name"] == "Cliente Antigo"
    assert update_response.status_code == 200
    assert update_response.json()["full_name"] == "Cliente Novo"


def test_admin_creates_promotion_with_uppercase_code(client, admin_headers):
    response = client.post(
        "/api/v1/admin/promotions",
        headers=admin_headers,
        json={
            "code": "lugano15",
            "description": "Desconto de teste",
            "type": "percentage",
            "value": "15",
            "min_order_cents": 3000,
            "max_uses": 10,
            "active": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["code"] == "LUGANO15"


def test_manager_can_create_promotion(client):
    use_admin_role("manager")
    try:
        response = client.post(
            "/api/v1/admin/promotions",
            json={
                "code": "gerente10",
                "description": "Campanha de gerente",
                "type": "percentage",
                "value": "10",
                "active": True,
            },
        )
    finally:
        clear_admin_role()

    assert response.status_code == 201
    assert response.json()["code"] == "GERENTE10"


def test_staff_cannot_list_promotions(client):
    use_admin_role("staff")
    try:
        response = client.get("/api/v1/admin/promotions")
    finally:
        clear_admin_role()

    assert response.status_code == 403
    assert response.json()["detail"] == "Permissao administrativa insuficiente"


def test_staff_cannot_view_reports(client):
    use_admin_role("staff")
    try:
        response = client.get("/api/v1/admin/reports")
    finally:
        clear_admin_role()

    assert response.status_code == 403
    assert response.json()["detail"] == "Permissao administrativa insuficiente"


def test_owner_lists_admin_users(client, fake_db):
    profile_id = "44444444-4444-4444-4444-444444444444"
    fake_db.tables["admin_users"].append(
        {
            "id": "55555555-5555-5555-5555-555555555555",
            "profile_id": profile_id,
            "role": "manager",
            "active": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    fake_db.tables["profiles"].append(
        {
            "id": profile_id,
            "full_name": "Gerente Lugano",
            "email": "gerente@lugano.test",
            "phone": None,
            "birth_date": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )

    use_admin_role("owner")
    try:
        response = client.get("/api/v1/admin/users")
    finally:
        clear_admin_role()

    assert response.status_code == 200
    assert response.json()[0]["email"] == "gerente@lugano.test"
    assert response.json()[0]["role"] == "manager"


def test_manager_cannot_list_admin_users(client):
    use_admin_role("manager")
    try:
        response = client.get("/api/v1/admin/users")
    finally:
        clear_admin_role()

    assert response.status_code == 403
    assert response.json()["detail"] == "Permissao administrativa insuficiente"


def test_owner_creates_admin_user(client, fake_db):
    profile_id = "66666666-6666-6666-6666-666666666666"
    fake_db.tables["profiles"].append(
        {
            "id": profile_id,
            "full_name": "Atendente Lugano",
            "email": "atendente@lugano.test",
            "phone": None,
            "birth_date": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )

    use_admin_role("owner")
    try:
        response = client.post(
            "/api/v1/admin/users",
            json={"profile_id": profile_id, "role": "staff", "active": True},
        )
    finally:
        clear_admin_role()

    assert response.status_code == 201
    assert response.json()["email"] == "atendente@lugano.test"
    assert response.json()["role"] == "staff"
    assert response.json()["active"] is True


def test_owner_deactivates_admin_user(client, fake_db):
    profile_id = "77777777-7777-7777-7777-777777777777"
    fake_db.tables["admin_users"].append(
        {
            "id": "88888888-8888-8888-8888-888888888888",
            "profile_id": profile_id,
            "role": "staff",
            "active": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    fake_db.tables["profiles"].append(
        {
            "id": profile_id,
            "full_name": "Equipe Lugano",
            "email": "equipe@lugano.test",
            "phone": None,
            "birth_date": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )

    use_admin_role("owner")
    try:
        response = client.patch(
            f"/api/v1/admin/users/{profile_id}",
            json={"active": False},
        )
    finally:
        clear_admin_role()

    assert response.status_code == 200
    assert response.json()["active"] is False


def test_admin_updates_promotion(client, admin_headers):
    promotion = client.post(
        "/api/v1/admin/promotions",
        headers=admin_headers,
        json={
            "code": "lugano20",
            "type": "percentage",
            "value": "20",
            "active": True,
        },
    ).json()

    response = client.patch(
        f"/api/v1/admin/promotions/{promotion['id']}",
        headers=admin_headers,
        json={"active": False, "description": "Campanha pausada"},
    )

    assert response.status_code == 200
    assert response.json()["active"] is False
    assert response.json()["description"] == "Campanha pausada"


def test_admin_reports_include_revenue_products_customers_and_coupons(
    client,
    admin_headers,
    fake_db,
):
    profile_id = "22222222-2222-2222-2222-222222222222"
    product_id = "33333333-3333-3333-3333-333333333333"
    promo_id = "44444444-4444-4444-4444-444444444444"
    fake_db.tables["profiles"].append(
        {
            "id": profile_id,
            "full_name": "Cliente Recorrente",
            "phone": "11999999999",
            "email": "recorrente@lugano.test",
            "birth_date": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    fake_db.tables["products"].append(
        {
            "id": product_id,
            "name": "Chocolate Quente Lugano",
            "category": "chocolateria",
            "price": "19.90",
            "available": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    fake_db.tables["promotions"].append(
        {
            "id": promo_id,
            "code": "LUGANO10",
            "description": "10% off",
            "type": "percentage",
            "value": "10",
            "uses_count": 1,
            "active": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    fake_db.tables["orders"].extend(
        [
            {
                "id": "55555555-5555-5555-5555-555555555555",
                "profile_id": profile_id,
                "address_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "status": "delivered",
                "payment_method": "pix",
                "payment_status": "paid",
                "subtotal": "39.80",
                "delivery_fee": "5.00",
                "discount": "3.98",
                "total": "40.82",
                "notes": None,
                "placed_at": "2026-06-20T12:00:00+00:00",
                "delivered_at": "2026-06-20T12:40:00+00:00",
                "updated_at": datetime.now(UTC).isoformat(),
                "order_items": [
                    {
                        "id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "product_id": product_id,
                        "quantity": 2,
                        "unit_price": "19.90",
                        "customization": None,
                    }
                ],
            },
            {
                "id": "66666666-6666-6666-6666-666666666666",
                "profile_id": profile_id,
                "address_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "status": "confirmed",
                "payment_method": "pix",
                "payment_status": "pending",
                "subtotal": "19.90",
                "delivery_fee": "5.00",
                "discount": "0.00",
                "total": "24.90",
                "notes": None,
                "placed_at": "2026-06-21T12:00:00+00:00",
                "delivered_at": None,
                "updated_at": datetime.now(UTC).isoformat(),
                "order_items": [
                    {
                        "id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                        "product_id": product_id,
                        "quantity": 1,
                        "unit_price": "19.90",
                        "customization": None,
                    }
                ],
            },
            {
                "id": "77777777-7777-7777-7777-777777777777",
                "profile_id": profile_id,
                "address_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "status": "cancelled",
                "payment_method": "pix",
                "payment_status": "pending",
                "subtotal": "19.90",
                "delivery_fee": "5.00",
                "discount": "0.00",
                "total": "24.90",
                "notes": None,
                "placed_at": "2026-06-21T13:00:00+00:00",
                "delivered_at": None,
                "updated_at": datetime.now(UTC).isoformat(),
                "order_items": [],
            },
        ]
    )
    fake_db.tables["promotion_usages"].append(
        {
            "id": "88888888-8888-8888-8888-888888888888",
            "promotion_id": promo_id,
            "profile_id": profile_id,
            "order_id": "55555555-5555-5555-5555-555555555555",
            "discount_applied": "3.98",
            "used_at": "2026-06-20T12:00:00+00:00",
        }
    )

    response = client.get(
        "/api/v1/admin/reports?date_from=2026-06-19&date_to=2026-06-22",
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["orders_count"] == 2
    assert body["summary"]["delivered_orders_count"] == 1
    assert body["summary"]["cancelled_orders_count"] == 1
    assert body["top_products"][0]["product_name"] == "Chocolate Quente Lugano"
    assert body["top_products"][0]["quantity_sold"] == 3
    assert body["recurring_customers"][0]["full_name"] == "Cliente Recorrente"
    assert body["coupon_usage"][0]["code"] == "LUGANO10"
    assert body["coupon_usage"][0]["uses_count"] == 1


def test_admin_updates_order_status(client, admin_headers, fake_db):
    order_id = "11111111-1111-1111-1111-111111111111"
    fake_db.tables["orders"].append(
        {
            "id": order_id,
            "profile_id": "22222222-2222-2222-2222-222222222222",
            "address_id": "33333333-3333-3333-3333-333333333333",
            "status": "pending",
            "payment_method": "pix",
            "payment_status": "pending",
            "subtotal": "19.90",
            "delivery_fee": "5.00",
            "discount": "0.00",
            "total": "24.90",
            "notes": None,
            "placed_at": datetime.now(UTC).isoformat(),
            "delivered_at": None,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )

    response = client.patch(
        f"/api/v1/admin/orders/{order_id}",
        headers=admin_headers,
        json={"status": "preparing", "payment_status": "paid"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "preparing"
    assert response.json()["payment_status"] == "paid"
    audit_log = fake_db.tables["audit_logs"][0]
    assert audit_log["action"] == "order.update"
    assert audit_log["entity_type"] == "order"
    assert audit_log["entity_id"] == order_id
    assert audit_log["before_data"]["status"] == "pending"
    assert audit_log["after_data"]["status"] == "preparing"
    assert audit_log["metadata"]["changed_fields"] == ["payment_status", "status"]


def test_admin_cannot_prepare_order_before_payment(client, admin_headers, fake_db):
    order_id = "11111111-1111-1111-1111-111111111111"
    fake_db.tables["orders"].append(
        {
            "id": order_id,
            "profile_id": "22222222-2222-2222-2222-222222222222",
            "status": "pending",
            "payment_status": "pending",
        }
    )

    response = client.patch(
        f"/api/v1/admin/orders/{order_id}",
        headers=admin_headers,
        json={"status": "preparing"},
    )

    assert response.status_code == 422
    assert "pagamento" in response.json()["detail"].lower()
    assert fake_db.tables["orders"][0]["status"] == "pending"


def test_admin_order_status_change_queues_notification(client, admin_headers, fake_db):
    previous_email_webhook = settings.notification_email_webhook_url
    previous_whatsapp_webhook = settings.notification_whatsapp_webhook_url
    previous_enabled = settings.notifications_enabled
    previous_email_enabled = settings.notification_email_enabled
    previous_whatsapp_enabled = settings.notification_whatsapp_enabled
    settings.notifications_enabled = True
    settings.notification_email_enabled = True
    settings.notification_whatsapp_enabled = True
    settings.notification_email_webhook_url = None
    settings.notification_whatsapp_webhook_url = None
    order_id = "11111111-1111-1111-1111-111111111111"
    profile_id = "22222222-2222-2222-2222-222222222222"
    fake_db.tables["profiles"].append(
        {
            "id": profile_id,
            "full_name": "Cliente Notificacao",
            "phone": "11999999999",
            "email": "cliente@lugano.test",
            "preferences": {"accepts_whatsapp": True},
            "birth_date": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    fake_db.tables["orders"].append(
        {
            "id": order_id,
            "profile_id": profile_id,
            "address_id": "33333333-3333-3333-3333-333333333333",
            "status": "pending",
            "payment_method": "pix",
            "payment_status": "pending",
            "subtotal": "19.90",
            "delivery_fee": "5.00",
            "discount": "0.00",
            "total": "24.90",
            "notes": None,
            "placed_at": datetime.now(UTC).isoformat(),
            "delivered_at": None,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )

    try:
        response = client.patch(
            f"/api/v1/admin/orders/{order_id}",
            headers=admin_headers,
            json={"status": "confirmed"},
        )
    finally:
        settings.notification_email_webhook_url = previous_email_webhook
        settings.notification_whatsapp_webhook_url = previous_whatsapp_webhook
        settings.notifications_enabled = previous_enabled
        settings.notification_email_enabled = previous_email_enabled
        settings.notification_whatsapp_enabled = previous_whatsapp_enabled

    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
    assert len(fake_db.tables["notification_events"]) == 2
    assert fake_db.tables["notification_events"][0]["event_type"] == "order_confirmed"


def test_admin_lists_orders_with_status_filter(client, admin_headers, fake_db):
    fake_db.tables["orders"].extend(
        [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "status": "pending",
                "profile_id": "22222222-2222-2222-2222-222222222222",
                "placed_at": datetime.now(UTC).isoformat(),
            },
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "status": "delivered",
                "profile_id": "22222222-2222-2222-2222-222222222222",
                "placed_at": datetime.now(UTC).isoformat(),
            },
        ]
    )

    response = client.get(
        "/api/v1/admin/orders?status=pending",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "pending"


def test_admin_order_detail_includes_customer_address_and_items(
    client,
    admin_headers,
    fake_db,
):
    order_id = "99999999-9999-9999-9999-999999999999"
    profile_id = "22222222-2222-2222-2222-222222222222"
    address_id = "33333333-3333-3333-3333-333333333333"
    product_id = "44444444-4444-4444-4444-444444444444"
    fake_db.tables["profiles"].append(
        {
            "id": profile_id,
            "full_name": "Cliente Delivery",
            "email": "cliente@lugano.test",
            "phone": "11999999999",
            "birth_date": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    fake_db.tables["addresses"].append(
        {
            "id": address_id,
            "profile_id": profile_id,
            "label": "Casa",
            "street": "Rua Lugano",
            "number": "100",
            "complement": None,
            "neighborhood": "Centro",
            "city": "Gramado",
            "zip_code": "00000000",
            "is_default": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    fake_db.tables["products"].append(
        {
            "id": product_id,
            "name": "Chocolate Quente Lugano",
            "description": None,
            "category": "chocolateria",
            "price": "19.90",
            "available": True,
            "image_url": None,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )
    fake_db.tables["orders"].append(
        {
            "id": order_id,
            "profile_id": profile_id,
            "address_id": address_id,
            "status": "pending",
            "payment_method": "pix",
            "payment_status": "pending",
            "subtotal": "19.90",
            "delivery_fee": "5.00",
            "discount": "0.00",
            "total": "24.90",
            "notes": "Sem canela",
            "placed_at": datetime.now(UTC).isoformat(),
            "delivered_at": None,
            "updated_at": datetime.now(UTC).isoformat(),
            "order_items": [
                {
                    "id": "55555555-5555-5555-5555-555555555555",
                    "product_id": product_id,
                    "quantity": 1,
                    "unit_price": "19.90",
                    "customization": None,
                    "created_at": datetime.now(UTC).isoformat(),
                }
            ],
        }
    )

    response = client.get(f"/api/v1/admin/orders/{order_id}", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["customer"]["full_name"] == "Cliente Delivery"
    assert body["address"]["street"] == "Rua Lugano"
    assert body["order_items"][0]["product"]["name"] == "Chocolate Quente Lugano"
