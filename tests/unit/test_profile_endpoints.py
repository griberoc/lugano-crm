from datetime import UTC, datetime

from app.api.v1.endpoints import profile as profile_endpoint
from app.main import app


def use_customer(fake_db, profile_id="11111111-1111-1111-1111-111111111111"):
    app.dependency_overrides[profile_endpoint.get_current_user] = lambda: {
        "id": profile_id,
        "email": "cliente@lugano.test",
        "access_token": "test-token",
    }
    app.dependency_overrides[profile_endpoint.get_authenticated_db] = lambda: fake_db
    return profile_id


def test_customer_updates_profile_preferences(client, fake_db):
    profile_id = use_customer(fake_db)
    fake_db.tables["profiles"].append(
        {
            "id": profile_id,
            "full_name": "Cliente Lugano",
            "phone": None,
            "email": "cliente@lugano.test",
            "birth_date": None,
            "preferences": {},
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )

    response = client.patch(
        "/api/v1/me/",
        json={
            "full_name": "Cliente Preferencial",
            "phone": "(11) 99999-9999",
            "birth_date": "1990-05-20",
            "preferences": {
                "preferred_contact": "whatsapp",
                "favorite_categories": ["cafeteria", "chocolateria"],
                "dietary_restrictions": ["sem lactose"],
                "accepts_promotions": True,
                "accepts_whatsapp": True,
                "notes": "Prefere chocolate intenso",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Cliente Preferencial"
    assert body["phone"] == "11999999999"
    assert body["preferences"]["preferred_contact"] == "whatsapp"
    assert body["preferences"]["favorite_categories"] == ["cafeteria", "chocolateria"]


def test_customer_manages_saved_addresses(client, fake_db):
    profile_id = use_customer(fake_db)

    first_response = client.post(
        "/api/v1/me/addresses",
        json={
            "label": "Casa",
            "street": "Rua Chocolate",
            "number": "10",
            "neighborhood": "Centro",
            "city": "Gramado",
            "zip_code": "95670000",
            "is_default": False,
        },
    )
    second_response = client.post(
        "/api/v1/me/addresses",
        json={
            "label": "Trabalho",
            "street": "Avenida Cafe",
            "number": "200",
            "neighborhood": "Planalto",
            "city": "Gramado",
            "zip_code": "95670001",
            "is_default": True,
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    first_address = first_response.json()
    second_address = second_response.json()
    assert first_address["is_default"] is True
    assert second_address["is_default"] is True
    assert fake_db.tables["addresses"][0]["is_default"] is False
    assert fake_db.tables["addresses"][1]["is_default"] is True

    patch_response = client.patch(
        f"/api/v1/me/addresses/{first_address['id']}",
        json={"label": "Casa principal", "is_default": True},
    )

    assert patch_response.status_code == 200
    assert patch_response.json()["label"] == "Casa principal"
    assert fake_db.tables["addresses"][0]["is_default"] is True
    assert fake_db.tables["addresses"][1]["is_default"] is False

    delete_response = client.delete(f"/api/v1/me/addresses/{second_address['id']}")

    assert delete_response.status_code == 204
    assert all(address["id"] != second_address["id"] for address in fake_db.tables["addresses"])
    assert all(address["profile_id"] == profile_id for address in fake_db.tables["addresses"])
