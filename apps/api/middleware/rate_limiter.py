"""Redis sliding-window rate limiter ve middleware."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from apps.api.core.exceptions import RateLimitException

if TYPE_CHECKING:
    from apps.api.core.config import Settings

logger = logging.getLogger("ygip.rate_limiter")

WINDOW_SECONDS = 60
PASSWORD_RESET_WINDOW_SECONDS = 3600
EXEMPT_PATHS = frozenset({"/health", "/ready"})
_IP_BASED_CATEGORIES = frozenset(
    {"auth", "auth_login", "auth_refresh", "password_reset"},
)


class RateLimiterBackend(ABC):
    """Rate limit sayaç backend arayüzü."""

    @abstractmethod
    async def increment_and_check(
        self,
        key: str,
        limit: int,
        window_seconds: int = WINDOW_SECONDS,
    ) -> tuple[bool, int]:
        """Sayaç artır; limit aşıldıysa (True, retry_after) döner."""


class InMemoryRateLimiterBackend(RateLimiterBackend):
    """Test ve Redis yokken kullanılan in-memory sliding window."""

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def increment_and_check(
        self,
        key: str,
        limit: int,
        window_seconds: int = WINDOW_SECONDS,
    ) -> tuple[bool, int]:
        now = time.time()
        window_start = now - window_seconds
        hits = [ts for ts in self._hits[key] if ts > window_start]
        hits.append(now)
        self._hits[key] = hits
        if len(hits) > limit:
            oldest = min(hits)
            retry_after = max(1, int(window_seconds - (now - oldest)) + 1)
            return True, retry_after
        return False, 0


class RedisRateLimiterBackend(RateLimiterBackend):
    """Redis sorted-set tabanlı sliding window."""

    def __init__(self, redis_url: str, *, fail_open: bool = True) -> None:
        from redis.asyncio import Redis

        self._redis: Redis = Redis.from_url(redis_url, decode_responses=True)
        self._fail_open = fail_open

    async def increment_and_check(
        self,
        key: str,
        limit: int,
        window_seconds: int = WINDOW_SECONDS,
    ) -> tuple[bool, int]:
        try:
            now = time.time()
            member = f"{now}:{key}"
            pipeline = self._redis.pipeline()
            pipeline.zremrangebyscore(key, 0, now - window_seconds)
            pipeline.zadd(key, {member: now})
            pipeline.zcard(key)
            pipeline.expire(key, window_seconds)
            results = await pipeline.execute()
        except Exception:
            logger.warning("rate_limiter_redis_error", exc_info=True)
            if self._fail_open:
                return False, 0
            return True, window_seconds

        count = int(results[2])
        if count > limit:
            oldest_scores = await self._redis.zrange(key, 0, 0, withscores=True)
            if oldest_scores:
                oldest_ts = float(oldest_scores[0][1])
                retry_after = max(1, int(window_seconds - (now - oldest_ts)) + 1)
            else:
                retry_after = window_seconds
            return True, retry_after
        return False, 0

    async def close(self) -> None:
        await self._redis.aclose()


def create_rate_limiter_backend(settings: Settings) -> RateLimiterBackend:
    """Redis bağlantısı başarısızsa in-memory fallback."""
    fail_open = settings.is_development
    try:
        return RedisRateLimiterBackend(settings.REDIS_URL, fail_open=fail_open)
    except Exception:
        logger.warning("redis_unavailable_using_in_memory_rate_limiter")
        return InMemoryRateLimiterBackend()


def resolve_rate_limit(path: str, settings: Settings) -> tuple[str | None, int, int]:
    """Endpoint kategorisine göre limit anahtarı, değer ve pencere süresi döner."""
    if path in EXEMPT_PATHS:
        return None, 0, WINDOW_SECONDS
    if path == "/api/v1/auth/login":
        return "auth_login", settings.RATE_LIMIT_AUTH, WINDOW_SECONDS
    if path == "/api/v1/auth/refresh":
        return "auth_refresh", settings.RATE_LIMIT_AUTH_REFRESH, WINDOW_SECONDS
    if path.startswith("/api/v1/auth/password-reset"):
        return (
            "password_reset",
            settings.RATE_LIMIT_PASSWORD_RESET,
            PASSWORD_RESET_WINDOW_SECONDS,
        )
    if path.startswith("/api/v1/auth"):
        return "auth", settings.RATE_LIMIT_AUTH, WINDOW_SECONDS
    if path == "/api/v1/chat":
        return None, 0, WINDOW_SECONDS
    return "general", settings.RATE_LIMIT_GENERAL, WINDOW_SECONDS


def build_rate_limit_key(category: str, request: Request) -> str:
    """Kategori bazlı Redis/in-memory anahtarı — Docs/03 §15 pattern."""
    client_ip = request.client.host if request.client else "unknown"
    if category in _IP_BASED_CATEGORIES:
        return f"rate_limit:ip:{client_ip}:{category}"
    if category == "chatbot":
        user_id = getattr(request.state, "user_id", None)
        if user_id is not None:
            return f"rate_limit:user:{user_id}:chat"
        return f"rate_limit:ip:{client_ip}:chat"
    if category == "pipeline":
        user_id = getattr(request.state, "user_id", None)
        if user_id is not None:
            return f"rate_limit:user:{user_id}:pipeline"
        return f"rate_limit:ip:{client_ip}:pipeline"
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        return f"rate_limit:user:{user_id}:general"
    return f"rate_limit:ip:{client_ip}:general"


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Endpoint kategorisine göre sliding-window rate limit."""

    def __init__(
        self,
        app: object,
        *,
        settings: Settings,
        backend: RateLimiterBackend | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._settings = settings
        self._backend = backend or create_rate_limiter_backend(settings)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        category, limit, window_seconds = resolve_rate_limit(
            request.url.path,
            self._settings,
        )
        if category is None or limit <= 0:
            return await call_next(request)

        key = build_rate_limit_key(category, request)
        exceeded, retry_after = await self._backend.increment_and_check(
            key,
            limit,
            window_seconds,
        )
        if exceeded:
            exc = RateLimitException(retry_after_seconds=retry_after)
            return _rate_limit_response(request, exc)

        return await call_next(request)


def _rate_limit_response(request: Request, exc: RateLimitException) -> Response:
    from starlette.responses import JSONResponse

    request_id = getattr(request.state, "request_id", "")
    headers = {"Retry-After": str(exc.retry_after_seconds)}
    if request_id:
        headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details or {},
            }
        },
        headers=headers,
    )


def rate_limit_dependency_factory(
    backend: RateLimiterBackend,
    settings: Settings,
    category: str,
    limit: int,
    *,
    window_seconds: int = WINDOW_SECONDS,
) -> Callable[[Request], None]:
    """Router seviyesinde kullanılabilecek rate limit dependency (auth iterasyonu için)."""

    async def _check(request: Request) -> None:
        key = build_rate_limit_key(category, request)
        exceeded, retry_after = await backend.increment_and_check(
            key,
            limit,
            window_seconds,
        )
        if exceeded:
            raise RateLimitException(retry_after_seconds=retry_after)

    return _check  # type: ignore[return-value]
