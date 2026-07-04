import argparse
import json

import httpx

from scripts.seed_initial_data import (
    SeedConfig,
    build_config,
    disable_products_not_in_seed,
    ensure_owner_profile_and_role,
    ensure_owner_user,
    load_seed_file,
    run_seed,
    upsert_by_field,
)


def mock_client(handler):
    return httpx.Client(
        base_url="https://supabase.test",
        transport=httpx.MockTransport(handler),
    )


def minimal_seed_file(tmp_path):
    path = tmp_path / "seed.json"
    path.write_text(
        json.dumps(
            {
                "loyalty_tiers": [],
                "products": [],
                "promotions": [],
                "operational_settings": [],
            }
        ),
        encoding="utf-8",
    )
    return path


def seed_config(**overrides):
    return SeedConfig(
        supabase_url="https://supabase.test",
        supabase_service_role_key="service-key",
        owner_email="owner@lugano.test",
        owner_password="secret-password",
        owner_full_name="Owner Lugano",
        disable_missing_products=False,
        **overrides,
    )


def test_load_seed_file_validates_required_lists(tmp_path):
    path = minimal_seed_file(tmp_path)

    data = load_seed_file(path)

    assert data["products"] == []


def test_run_seed_dry_run_does_not_call_network(tmp_path):
    path = minimal_seed_file(tmp_path)
    config = seed_config(seed_file=path, dry_run=True)

    run_seed(config)


def test_upsert_by_field_inserts_when_record_does_not_exist():
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.method == "POST":
            return httpx.Response(
                201,
                json=[{"id": "product-id", "name": "Cappuccino Lugano"}],
            )
        return httpx.Response(500)

    with mock_client(handler) as client:
        result = upsert_by_field(
            client,
            seed_config(),
            "products",
            "name",
            {"name": "Cappuccino Lugano", "price": "16.90"},
        )

    assert result["id"] == "product-id"
    assert requests == [("GET", "/rest/v1/products"), ("POST", "/rest/v1/products")]


def test_upsert_by_field_updates_existing_record():
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[{"id": "product-id", "name": "Cappuccino Lugano"}],
            )
        if request.method == "PATCH":
            return httpx.Response(
                200,
                json=[{"id": "product-id", "name": "Cappuccino Lugano"}],
            )
        return httpx.Response(500)

    with mock_client(handler) as client:
        result = upsert_by_field(
            client,
            seed_config(),
            "products",
            "name",
            {"name": "Cappuccino Lugano", "price": "17.90"},
        )

    assert result["id"] == "product-id"
    assert requests == [("GET", "/rest/v1/products"), ("PATCH", "/rest/v1/products")]


def test_disable_products_not_in_seed_marks_only_extra_available_products():
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path, dict(request.url.params)))
        if request.method == "GET":
            return httpx.Response(
                200,
                json=[
                    {"name": "Brownie", "available": True},
                    {"name": "Produto antigo", "available": True},
                    {"name": "Produto ja indisponivel", "available": False},
                ],
            )
        if request.method == "PATCH":
            return httpx.Response(204)
        return httpx.Response(500)

    with mock_client(handler) as client:
        disable_products_not_in_seed(
            client,
            seed_config(),
            [{"name": "Brownie"}],
        )

    assert requests == [
        ("GET", "/rest/v1/products", {"select": "name,available"}),
        ("PATCH", "/rest/v1/products", {"name": "eq.Produto antigo"}),
    ]


def test_ensure_owner_user_creates_when_missing():
    def handler(request):
        if request.method == "GET" and request.url.path == "/auth/v1/admin/users":
            return httpx.Response(200, json={"users": []})
        if request.method == "POST" and request.url.path == "/auth/v1/admin/users":
            return httpx.Response(
                201,
                json={"id": "owner-id", "email": "owner@lugano.test"},
            )
        return httpx.Response(500)

    with mock_client(handler) as client:
        user = ensure_owner_user(client, seed_config())

    assert user["id"] == "owner-id"


def test_ensure_owner_profile_and_role_upserts_profile_and_admin_user():
    paths = []

    def handler(request):
        paths.append(str(request.url.path))
        return httpx.Response(201, json=[{"id": "ok"}])

    with mock_client(handler) as client:
        ensure_owner_profile_and_role(
            client,
            seed_config(),
            {"id": "owner-id", "email": "owner@lugano.test"},
        )

    assert paths == ["/rest/v1/profiles", "/rest/v1/admin_users"]


def test_build_config_reads_seed_owner_env(monkeypatch, tmp_path):
    seed_file = minimal_seed_file(tmp_path)
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    monkeypatch.setenv("SEED_OWNER_EMAIL", "owner@lugano.test")
    monkeypatch.setenv("SEED_OWNER_PASSWORD", "secret-password")
    monkeypatch.setenv("SEED_OWNER_FULL_NAME", "Owner Teste")

    args = argparse.Namespace(
        supabase_url=None,
        supabase_service_role_key=None,
        owner_email=None,
        owner_password=None,
        owner_full_name=None,
        seed_file=str(seed_file),
        dry_run=False,
        disable_missing_products=False,
    )

    config = build_config(args)

    assert config.owner_email == "owner@lugano.test"
    assert config.owner_full_name == "Owner Teste"
