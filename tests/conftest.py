from collections import defaultdict
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.admin import get_admin_db
from app.core.config import settings
from app.main import app


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, db, name):
        self.db = db
        self.name = name
        self.rows = db.tables[name]
        self.pending_data = None
        self.filters = []
        self.single_result = False
        self.limit_count = None

    def select(self, *_args):
        return self

    def insert(self, data):
        self.pending_data = data
        return self

    def update(self, data):
        self.pending_data = data
        return self

    def delete(self):
        self.pending_data = "__delete__"
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, set(values)))
        return self

    def lte(self, field, value):
        self.filters.append(("lte", field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def range(self, *_args):
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def single(self):
        self.single_result = True
        return self

    def execute(self):
        if self.pending_data == "__delete__":
            self.rows[:] = [row for row in self.rows if not self._matches(row)]
            return FakeResponse([])

        if self.pending_data is not None and self._is_insert():
            payloads = (
                self.pending_data
                if isinstance(self.pending_data, list)
                else [self.pending_data]
            )
            inserted = []
            for payload in payloads:
                row = {
                    "id": str(uuid4()),
                    "created_at": self.db.now,
                    "updated_at": self.db.now,
                    **self.db.defaults.get(self.name, {}),
                    **payload,
                }
                self.rows.append(row)
                inserted.append(row)
            return FakeResponse(inserted)

        if self.pending_data is not None:
            updated = []
            for row in self._filtered_rows():
                row.update(self.pending_data)
                row["updated_at"] = self.db.now
                updated.append(row)
            return FakeResponse(updated)

        rows = self._filtered_rows()
        if self.limit_count is not None:
            rows = rows[: self.limit_count]
        if self.single_result:
            return FakeResponse(rows[0] if rows else None)
        return FakeResponse(rows)

    def _is_insert(self):
        return not self.filters

    def _filtered_rows(self):
        return [row for row in self.rows if self._matches(row)]

    def _matches(self, row):
        for operator, field, value in self.filters:
            row_value = row.get(field)
            if operator == "eq" and row_value != value:
                return False
            if operator == "in" and row_value not in value:
                return False
            if operator == "lte" and row_value > value:
                return False
        return True


class FakeRpc:
    def execute(self):
        return FakeResponse(None)


class FakeSupabase:
    def __init__(self):
        self.now = datetime.now(UTC).isoformat()
        self.tables = defaultdict(list)
        self.defaults = {
            "promotions": {"uses_count": 0},
        }

    def table(self, name):
        return FakeTable(self, name)

    def rpc(self, *_args, **_kwargs):
        return FakeRpc()


@pytest.fixture
def fake_db():
    return FakeSupabase()


@pytest.fixture
def client(fake_db):
    previous_admin_key = settings.admin_api_key
    settings.admin_api_key = "test-admin-key"

    def override_admin_db():
        return fake_db

    app.dependency_overrides[get_admin_db] = override_admin_db

    with TestClient(app) as test_client:
        yield test_client

    settings.admin_api_key = previous_admin_key
    app.dependency_overrides.clear()


@pytest.fixture
def admin_headers():
    return {"X-Admin-Key": "test-admin-key"}
