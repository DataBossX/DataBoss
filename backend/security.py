"""Security middleware and dependencies: API-key auth, rate limiting, headers.

Auth and rate limiting are *opt-in*: they activate only when configured via
the environment (``API_KEYS`` / ``RATE_LIMIT_PER_MINUTE``), so existing
deployments and the test suite keep working unchanged. Config is read at call
time (not import time) so it can be toggled in tests.

Security response headers are always applied — there is no downside.
"""

import time
from collections import deque
from threading import Lock

from fastapi import Header, Request

import config
from errors import ApiError

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-XSS-Protection": "0",
}

# Paths that never require auth / rate limiting (health probes, metrics scrape).
EXEMPT_PATHS = {"/api/health", "/metrics", "/docs", "/openapi.json", "/redoc"}


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency. No-op unless API_KEYS is configured."""
    if not config.API_KEYS:
        return
    if x_api_key is None or x_api_key not in config.API_KEYS:
        raise ApiError(401, "Missing or invalid API key")


class RateLimiter:
    """In-process sliding-window limiter keyed by client identifier."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()

    def check(self, identifier: str, limit: int, window: float) -> float | None:
        """Return None if allowed, else seconds to wait before retrying."""
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(identifier, deque())
            while q and now - q[0] >= window:
                q.popleft()
            if len(q) >= limit:
                return round(window - (now - q[0]), 2)
            q.append(now)
            return None


limiter = RateLimiter()


def _client_id(request: Request) -> str:
    key = request.headers.get("x-api-key")
    if key:
        return f"key:{key}"
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


async def security_middleware(request: Request, call_next):
    """Apply rate limiting (opt-in) and security headers."""
    limit = config.RATE_LIMIT_PER_MINUTE
    if limit and request.url.path not in EXEMPT_PATHS:
        retry_after = limiter.check(_client_id(request), limit, config.RATE_LIMIT_WINDOW)
        if retry_after is not None:
            from fastapi.responses import JSONResponse

            resp = JSONResponse(status_code=429, content={"error": "Rate limit exceeded"})
            resp.headers["Retry-After"] = str(retry_after)
            for k, v in SECURITY_HEADERS.items():
                resp.headers[k] = v
            return resp

    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers[k] = v
    return response
