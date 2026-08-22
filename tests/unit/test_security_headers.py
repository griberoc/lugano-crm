from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security_headers import SecurityHeadersMiddleware


def make_client(*, hsts_enabled: bool) -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=hsts_enabled)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return TestClient(app)


def test_api_security_headers_are_applied():
    response = make_client(hsts_enabled=False).get("/health")

    assert response.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
        "form-action 'none'"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["permissions-policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )
    assert "strict-transport-security" not in response.headers


def test_hsts_is_applied_only_when_enabled():
    response = make_client(hsts_enabled=True).get("/health")

    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
