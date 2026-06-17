"""Rate limiter unit testleri."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock

import pytest
from apps.api.core.config import Settings
from apps.api.main import create_app
from apps.api.middleware.rate_limiter import InMemoryRateLimiterBackend, RedisRateLimiterBackend
from httpx import ASGITransport, AsyncClient


class _FakeDbSession:
    """Auth login handler'ının DB bağımlılığını mock'lar — yalnızca rate limit testi."""

    def add(self, _obj: object) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def execute(self, *_args: object, **_kwargs: object) -> MagicMock:
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        return result


@asynccontextmanager
async def _fake_session_scope():
    session = _FakeDbSession()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise


class _FakeSessionFactory:
    def __call__(self):
        return _fake_session_scope()


def _attach_fake_db(app: object) -> None:
    app.state.session_factory = _FakeSessionFactory()  # type: ignore[attr-defined]


@pytest.fixture
def auth_rate_settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/ygip_test",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET_KEY="test-secret",
        RATE_LIMIT_AUTH=10,
        RATE_LIMIT_AUTH_REFRESH=20,
        RATE_LIMIT_PASSWORD_RESET=3,
        RATE_LIMIT_GENERAL=100,
        ENVIRONMENT="development",
    )


@pytest.mark.asyncio
async def test_auth_rate_limit_blocks_after_ten_requests(
    auth_rate_settings: Settings,
) -> None:
    backend = InMemoryRateLimiterBackend()
    app = create_app(settings=auth_rate_settings, rate_limiter_backend=backend)
    _attach_fake_db(app)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(10):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": "user@example.com", "password": "WrongPass1"},
            )
            assert response.status_code != 429

        blocked = await client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "WrongPass1"},
        )
        assert blocked.status_code == 429
        payload = blocked.json()
        assert payload["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert "retry_after_seconds" in payload["error"]["details"]
        assert blocked.headers.get("Retry-After") is not None


@pytest.mark.asyncio
async def test_refresh_rate_limit_blocks_after_twenty_requests(
    auth_rate_settings: Settings,
) -> None:
    backend = InMemoryRateLimiterBackend()
    app = create_app(settings=auth_rate_settings, rate_limiter_backend=backend)
    _attach_fake_db(app)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(20):
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "invalid-token"},
            )
            assert response.status_code != 429

        blocked = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_password_reset_rate_limit_blocks_after_three_requests(
    auth_rate_settings: Settings,
) -> None:
    backend = InMemoryRateLimiterBackend()
    app = create_app(settings=auth_rate_settings, rate_limiter_backend=backend)
    _attach_fake_db(app)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            response = await client.post(
                "/api/v1/auth/password-reset/complete",
                json={"token": "bad-token", "new_password": "NewPass1"},
            )
            assert response.status_code != 429

        blocked = await client.post(
            "/api/v1/auth/password-reset/complete",
            json={"token": "bad-token", "new_password": "NewPass1"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_health_endpoints_are_exempt_from_rate_limit(
    auth_rate_settings: Settings,
) -> None:
    backend = InMemoryRateLimiterBackend()
    app = create_app(settings=auth_rate_settings, rate_limiter_backend=backend)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(20):
            response = await client.get("/health")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_redis_backend_fail_closed_blocks_on_error() -> None:
    backend = RedisRateLimiterBackend("redis://localhost:6379/0", fail_open=False)
    backend._redis = MagicMock()  # type: ignore[method-assign]
    backend._redis.pipeline.side_effect = RuntimeError("redis down")

    exceeded, retry_after = await backend.increment_and_check(
        "rate_limit:ip:1.2.3.4:auth_login",
        10,
    )

    assert exceeded is True
    assert retry_after == 60
