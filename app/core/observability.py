import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


def configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger = logging.getLogger("lugano.requests")
        request_id = request.headers.get("x-request-id") or str(uuid4())
        started_at = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.exception(
                "Unhandled request error method=%s path=%s request_id=%s "
                "duration_ms=%s client=%s",
                request.method,
                request.url.path,
                request_id,
                duration_ms,
                request.client.host if request.client else None,
            )
            raise

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        if response.status_code >= 500:
            logger.error(
                "HTTP request failed status=%s method=%s path=%s request_id=%s "
                "duration_ms=%s",
                response.status_code,
                request.method,
                request.url.path,
                request_id,
                duration_ms,
            )

        response.headers["X-Request-ID"] = request_id
        return response
