from app.core.config import settings


class FakeReadyDb:
    def table(self, name):
        assert name == "products"
        return self

    def select(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return None


class BrokenReadyDb(FakeReadyDb):
    def execute(self):
        raise RuntimeError("supabase offline")


def test_health_liveness_returns_request_id(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"]


def test_readiness_checks_supabase(client, monkeypatch):
    from app import main as main_module

    previous = settings.healthcheck_supabase_enabled
    settings.healthcheck_supabase_enabled = True
    monkeypatch.setattr(main_module, "get_supabase_admin", lambda: FakeReadyDb())

    try:
        response = client.get("/health/ready")
    finally:
        settings.healthcheck_supabase_enabled = previous

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["checks"]["supabase"] == "ok"


def test_readiness_fails_when_supabase_is_unavailable(client, monkeypatch):
    from app import main as main_module

    previous = settings.healthcheck_supabase_enabled
    settings.healthcheck_supabase_enabled = True
    monkeypatch.setattr(main_module, "get_supabase_admin", lambda: BrokenReadyDb())

    try:
        response = client.get("/health/ready")
    finally:
        settings.healthcheck_supabase_enabled = previous

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["supabase"] == "failed"
