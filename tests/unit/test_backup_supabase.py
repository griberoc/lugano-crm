import argparse

import httpx
import pytest

from scripts.backup_supabase import (
    BackupConfig,
    BackupError,
    build_config,
    export_table,
    parse_tables,
    table_order_column,
)


def mock_client(handler):
    return httpx.Client(
        base_url="https://supabase.test",
        transport=httpx.MockTransport(handler),
    )


def backup_config(**overrides):
    return BackupConfig(
        supabase_url="https://supabase.test",
        supabase_service_role_key="service-key",
        output_dir=overrides.pop("output_dir"),
        page_size=overrides.pop("page_size", 2),
        **overrides,
    )


def test_parse_tables_uses_defaults_when_empty():
    tables = parse_tables(None)

    assert "orders" in tables
    assert "audit_logs" in tables


def test_parse_tables_splits_custom_list():
    assert parse_tables("orders, audit_logs") == ("orders", "audit_logs")


def test_table_order_column_uses_key_for_settings():
    assert table_order_column("operational_settings") == "key"
    assert table_order_column("orders") == "id"


def test_export_table_paginates_until_short_page(tmp_path):
    calls = []

    def handler(request):
        calls.append(dict(request.url.params))
        offset = int(request.url.params["offset"])
        if offset == 0:
            return httpx.Response(200, json=[{"id": "1"}, {"id": "2"}])
        return httpx.Response(200, json=[{"id": "3"}])

    with mock_client(handler) as client:
        rows = export_table(client, backup_config(output_dir=tmp_path), "orders")

    assert rows == [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    assert calls[0]["limit"] == "2"
    assert calls[0]["order"] == "id.asc"
    assert calls[1]["offset"] == "2"


def test_export_table_rejects_non_list_response(tmp_path):
    def handler(_request):
        return httpx.Response(200, json={"error": "not a list"})

    with mock_client(handler) as client:
        with pytest.raises(BackupError):
            export_table(client, backup_config(output_dir=tmp_path), "orders")


def test_build_config_rejects_invalid_page_size(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    args = argparse.Namespace(
        supabase_url=None,
        supabase_service_role_key=None,
        output_dir=str(tmp_path),
        tables=None,
        page_size="0",
    )

    with pytest.raises(BackupError):
        build_config(args)
