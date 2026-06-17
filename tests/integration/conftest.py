"""Integration test fixtures — async HTTP client ve DB."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from apps.api.core.config import Settings
from apps.api.core.security import hash_password
from apps.api.main import create_app
from apps.api.middleware.rate_limiter import InMemoryRateLimiterBackend
from httpx import ASGITransport, AsyncClient
from packages.shared.enums import UserRole
from packages.shared.models.user import User
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_LOCAL_DEV_URL = "postgresql+asyncpg://ygip:ygip_dev_pass@localhost:5432/ygip_dev"
_CI_TEST_URL = "postgresql+asyncpg://test:test@localhost:5432/ygip_test"


def _candidate_database_urls() -> list[str]:
    if env_url := os.environ.get("DATABASE_URL"):
        return [env_url]
    return [_LOCAL_DEV_URL, _CI_TEST_URL]


async def _can_connect(url: str) -> bool:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def database_url() -> str:
    for url in _candidate_database_urls():
        import asyncio

        if asyncio.run(_can_connect(url)):
            return url
    pytest.skip("PostgreSQL not available for integration tests")


@pytest.fixture
def test_settings(database_url: str) -> Settings:
    return Settings(
        DATABASE_URL=database_url,
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET_KEY="test-secret-key",
        CORS_ORIGINS=["http://localhost:3000"],
        ENVIRONMENT="development",
    )


@pytest.fixture
async def api_client(test_settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(
        settings=test_settings,
        rate_limiter_backend=InMemoryRateLimiterBackend(),
    )
    engine = create_async_engine(
        test_settings.DATABASE_URL,
        pool_size=test_settings.DB_POOL_SIZE,
        max_overflow=test_settings.DB_MAX_OVERFLOW,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    app.state.settings = test_settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await engine.dispose()


TEST_USER_PASSWORD = "TestPass1"


@dataclass(frozen=True)
class AuthTestUser:
    id: uuid.UUID
    email: str
    password: str
    role: UserRole


@pytest.fixture
async def active_test_user(database_url: str) -> AsyncIterator[AuthTestUser]:
    """Aktif test kullanıcısı — auth integration testleri için."""
    user_id = uuid.uuid4()
    email = f"auth-active-{user_id}@example.com"
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                password_hash=hash_password(TEST_USER_PASSWORD),
                full_name="Auth Test User",
                role=UserRole.VIEWER,
                is_active=True,
            )
        )
        await session.commit()

    credentials = AuthTestUser(
        id=user_id,
        email=email,
        password=TEST_USER_PASSWORD,
        role=UserRole.VIEWER,
    )
    yield credentials

    async with session_factory() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def inactive_test_user(database_url: str) -> AsyncIterator[AuthTestUser]:
    """Pasif test kullanıcısı."""
    user_id = uuid.uuid4()
    email = f"auth-inactive-{user_id}@example.com"
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                password_hash=hash_password(TEST_USER_PASSWORD),
                full_name="Inactive Auth User",
                role=UserRole.VIEWER,
                is_active=False,
            )
        )
        await session.commit()

    credentials = AuthTestUser(
        id=user_id,
        email=email,
        password=TEST_USER_PASSWORD,
        role=UserRole.VIEWER,
    )
    yield credentials

    async with session_factory() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def admin_test_user(database_url: str) -> AsyncIterator[AuthTestUser]:
    """Admin test kullanıcısı — user CRUD integration testleri için."""
    user_id = uuid.uuid4()
    email = f"admin-{user_id}@example.com"
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                password_hash=hash_password(TEST_USER_PASSWORD),
                full_name="Admin Test User",
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await session.commit()

    credentials = AuthTestUser(
        id=user_id,
        email=email,
        password=TEST_USER_PASSWORD,
        role=UserRole.ADMIN,
    )
    yield credentials

    async with session_factory() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def viewer_test_user(database_url: str) -> AsyncIterator[AuthTestUser]:
    """Viewer test kullanıcısı — RBAC deny testleri için."""
    user_id = uuid.uuid4()
    email = f"viewer-{user_id}@example.com"
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                email=email,
                password_hash=hash_password(TEST_USER_PASSWORD),
                full_name="Viewer Test User",
                role=UserRole.VIEWER,
                is_active=True,
            )
        )
        await session.commit()

    credentials = AuthTestUser(
        id=user_id,
        email=email,
        password=TEST_USER_PASSWORD,
        role=UserRole.VIEWER,
    )
    yield credentials

    async with session_factory() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
    await engine.dispose()


async def login_and_get_token(client: AsyncClient, user: AuthTestUser) -> str:
    """Login yapıp access token döner."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": user.password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
