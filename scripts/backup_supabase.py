import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TABLES = (
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
    "notification_events",
    "audit_logs",
    "admin_users",
    "operational_settings",
    "data_retention_policies",
)
ORDER_COLUMNS = {
    "operational_settings": "key",
    "data_retention_policies": "key",
}


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupConfig:
    supabase_url: str
    supabase_service_role_key: str
    output_dir: Path
    tables: tuple[str, ...] = DEFAULT_TABLES
    page_size: int = 1000


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
        raise BackupError(
            f"Missing {env_name}. Provide CLI option or environment value."
        )
    return result


def service_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }


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
    expected_status: int,
    **kwargs: Any,
) -> Any:
    response = client.request(method, path, **kwargs)
    body = parse_body(response)
    if response.status_code != expected_status:
        raise BackupError(
            f"{method} {path} expected {expected_status}, "
            f"got {response.status_code}: {body}"
        )
    return body


def timestamp_slug() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_output_dir() -> Path:
    return ROOT_DIR / "backups" / f"supabase-{timestamp_slug()}"


def table_order_column(table: str) -> str:
    return ORDER_COLUMNS.get(table, "id")


def export_table(
    client: httpx.Client,
    config: BackupConfig,
    table: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = request_json(
            client,
            "GET",
            f"/rest/v1/{table}",
            expected_status=200,
            headers=service_headers(config.supabase_service_role_key),
            params={
                "select": "*",
                "order": f"{table_order_column(table)}.asc",
                "limit": str(config.page_size),
                "offset": str(offset),
            },
        )
        if not isinstance(page, list):
            raise BackupError(f"Unexpected response for table {table}: {page}")
        rows.extend(page)
        if len(page) < config.page_size:
            break
        offset += config.page_size
    return rows


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def run_backup(config: BackupConfig) -> dict[str, Any]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "source": config.supabase_url,
        "tables": {},
        "warning": "Contains sensitive production data. Do not commit this folder.",
    }

    with httpx.Client(base_url=config.supabase_url.rstrip("/"), timeout=60) as client:
        for table in config.tables:
            rows = export_table(client, config, table)
            write_json(config.output_dir / f"{table}.json", rows)
            manifest["tables"][table] = {"rows": len(rows)}
            print(f"[OK] {table}: {len(rows)} rows")

    write_json(config.output_dir / "manifest.json", manifest)
    print(f"\nBackup written to {config.output_dir}")
    return manifest


def parse_tables(value: str | None) -> tuple[str, ...]:
    if not value:
        return DEFAULT_TABLES
    tables = tuple(item.strip() for item in value.split(",") if item.strip())
    if not tables:
        raise BackupError("At least one table must be selected.")
    return tables


def build_config(args: argparse.Namespace) -> BackupConfig:
    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else default_output_dir()
    )
    page_size = int(args.page_size)
    if page_size < 1 or page_size > 5000:
        raise BackupError("page_size must be between 1 and 5000.")
    return BackupConfig(
        supabase_url=env_or_arg(args.supabase_url, "SUPABASE_URL"),
        supabase_service_role_key=env_or_arg(
            args.supabase_service_role_key,
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
        output_dir=output_dir,
        tables=parse_tables(args.tables),
        page_size=page_size,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta backup logico das tabelas publicas do Lugano CRM.",
    )
    parser.add_argument("--env-file", default=".env.staging")
    parser.add_argument("--supabase-url")
    parser.add_argument("--supabase-service-role-key")
    parser.add_argument("--output-dir")
    parser.add_argument("--tables")
    parser.add_argument("--page-size", default="1000")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(ROOT_DIR / ".env")
    if args.env_file:
        load_dotenv((ROOT_DIR / args.env_file).resolve(), override=True)

    try:
        run_backup(build_config(args))
    except BackupError as exc:
        print(f"\n[FAIL] {exc}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"\n[FAIL] HTTP error: {exc}", file=sys.stderr)
        return 1

    print("\nLogical backup finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
