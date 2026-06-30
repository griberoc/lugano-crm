from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window-ish rate limiter backed by in-memory timestamps."""

    def __init__(
        self,
        app,
        *,
        enabled: bool,
        requests_limit: int,
        window_seconds: int,
        exempt_paths: set[str] | None = None,
        trust_proxy_headers: bool = False,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.exempt_paths = exempt_paths or set()
        self.trust_proxy_headers = trust_proxy_headers
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if self._should_skip(request):
            return await call_next(request)

        now = time.monotonic()
        key = self._client_key(request)
        hits = self._hits[key]
        cutoff = now - self.window_seconds

        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= self.requests_limit:
            retry_after = max(1, int(self.window_seconds - (now - hits[0])))
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Muitas requisicoes. Tente novamente em alguns segundos."
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.requests_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(retry_after),
                },
            )

        hits.append(now)
        remaining = max(0, self.requests_limit - len(hits))
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(self.window_seconds)
        return response

    def _should_skip(self, request: Request) -> bool:
        return (
            not self.enabled
            or self.requests_limit <= 0
            or self.window_seconds <= 0
            or request.method == "OPTIONS"
            or request.url.path in self.exempt_paths
        )

    def _client_key(self, request: Request) -> str:
        if self.trust_proxy_headers:
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                return forwarded_for.split(",", maxsplit=1)[0].strip()

            real_ip = request.headers.get("x-real-ip")
            if real_ip:
                return real_ip.strip()

        if request.client:
            return request.client.host

        return "unknown"
