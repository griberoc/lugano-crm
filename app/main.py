import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.observability import RequestLoggingMiddleware, configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.client import get_supabase_admin

logger = logging.getLogger("lugano.health")
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Supabase clients are created lazily by the dependency layer.
    yield


app = FastAPI(
    title="Lugano CRM",
    description=(
        "API para CRM de cafeteria e chocolateria, "
        "com delivery, fidelidade e promocoes"
    ),
    version="0.1.0",
    docs_url="/docs" if not settings.is_deployed else None,
    redoc_url="/redoc" if not settings.is_deployed else None,
    lifespan=lifespan,
)

app.add_middleware(
    RateLimitMiddleware,
    enabled=settings.rate_limit_enabled,
    requests_limit=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
    exempt_paths=settings.rate_limit_exempt_path_set,
    trust_proxy_headers=settings.rate_limit_trust_proxy_headers,
)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=settings.cors_allowed_methods,
    allow_headers=settings.cors_allowed_headers,
)
app.add_middleware(SecurityHeadersMiddleware, hsts_enabled=settings.is_deployed)

app.include_router(api_router)


@app.get("/health", tags=["infra"])
async def health_check():
    return {
        "status": "ok",
        "env": settings.app_env,
        "service": settings.monitoring_service_name,
        "version": app.version,
    }


@app.get("/health/ready", tags=["infra"])
async def readiness_check():
    checks = {"api": "ok", "supabase": "skipped"}
    http_status = 200

    if settings.healthcheck_supabase_enabled:
        try:
            (
                get_supabase_admin()
                .table("products")
                .select("id")
                .limit(1)
                .execute()
            )
            checks["supabase"] = "ok"
        except Exception as exc:
            checks["supabase"] = "failed"
            http_status = 503
            logger.exception("Supabase readiness check failed: %s", exc)

    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ready" if http_status == 200 else "degraded",
            "env": settings.app_env,
            "service": settings.monitoring_service_name,
            "checks": checks,
        },
    )
