from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.rate_limit import RateLimitMiddleware


def make_client(
    limit: int = 2,
    exempt_paths: set[str] | None = None,
    trust_proxy_headers: bool = False,
) -> TestClient:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        enabled=True,
        requests_limit=limit,
        window_seconds=60,
        exempt_paths=exempt_paths or set(),
        trust_proxy_headers=trust_proxy_headers,
    )

    @app.get("/limited")
    async def limited():
        return {"ok": True}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return TestClient(app)


def test_rate_limit_blocks_after_limit():
    client = make_client(limit=2)

    first = client.get("/limited")
    second = client.get("/limited")
    blocked = client.get("/limited")

    assert first.status_code == 200
    assert second.status_code == 200
    assert blocked.status_code == 429
    assert blocked.json()["detail"] == (
        "Muitas requisicoes. Tente novamente em alguns segundos."
    )
    assert blocked.headers["Retry-After"]
    assert blocked.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limit_exempts_paths():
    client = make_client(limit=1, exempt_paths={"/health"})

    first = client.get("/health")
    second = client.get("/health")
    limited = client.get("/limited")
    blocked = client.get("/limited")

    assert first.status_code == 200
    assert second.status_code == 200
    assert limited.status_code == 200
    assert blocked.status_code == 429


def test_rate_limit_ignores_spoofed_forwarded_for_by_default():
    client = make_client(limit=1)

    first = client.get("/limited", headers={"X-Forwarded-For": "10.0.0.1"})
    blocked = client.get("/limited", headers={"X-Forwarded-For": "10.0.0.2"})

    assert first.status_code == 200
    assert blocked.status_code == 429


def test_rate_limit_can_trust_proxy_headers_when_enabled():
    client = make_client(limit=1, trust_proxy_headers=True)

    first = client.get("/limited", headers={"X-Forwarded-For": "10.0.0.1"})
    second = client.get("/limited", headers={"X-Forwarded-For": "10.0.0.2"})

    assert first.status_code == 200
    assert second.status_code == 200
