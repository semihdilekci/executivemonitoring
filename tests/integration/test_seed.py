"""Seed script integration testleri."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from apps.api.main import create_app
from apps.api.middleware.rate_limiter import InMemoryRateLimiterBackend
from httpx import ASGITransport, AsyncClient
from packages.shared.models.keyword import Keyword
from packages.shared.models.newsletter_template import NewsletterTemplate
from packages.shared.models.notification_preference import NotificationPreference
from packages.shared.models.source import Source
from packages.shared.models.system_setting import SystemSetting
from packages.shared.models.user import User
from scripts.seed import SEED_ADMIN_EMAIL, SEED_DEV_PASSWORD, run_seed
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def seed_database(database_url: str) -> AsyncIterator[None]:
    """Seed test verisini temizler ve test sonrası siler."""
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        await session.execute(delete(NotificationPreference))
        await session.execute(delete(User).where(User.email.like("%@ygip.test")))
        await session.execute(delete(SystemSetting))
        await session.execute(delete(NewsletterTemplate))
        await session.execute(delete(Source))
        await session.execute(delete(Keyword))
        await session.commit()

    yield

    async with session_factory() as session:
        await session.execute(delete(NotificationPreference))
        await session.execute(delete(User).where(User.email.like("%@ygip.test")))
        await session.execute(delete(SystemSetting))
        await session.execute(delete(NewsletterTemplate))
        await session.execute(delete(Source))
        await session.execute(delete(Keyword))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_is_idempotent(seed_database: None, database_url: str) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        first = await run_seed(session)
        await session.commit()
        second = await run_seed(session)
        await session.commit()

    assert first.users.created == 3
    assert first.system_settings.created == 9
    assert first.newsletter_templates.created == 3
    assert first.sources.created == 66
    assert first.notification_preferences.created == 3

    assert second.users.created == 0
    assert second.users.skipped == 3
    assert second.system_settings.created == 0
    assert second.system_settings.skipped == 9
    assert second.newsletter_templates.created == 0
    assert second.newsletter_templates.skipped == 3
    assert second.sources.created == 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_seed_admin_can_login(
    seed_database: None,
    database_url: str,
    test_settings,
) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await run_seed(session)
        await session.commit()
    await engine.dispose()

    app = create_app(
        settings=test_settings,
        rate_limiter_backend=InMemoryRateLimiterBackend(),
    )
    test_engine = create_async_engine(
        test_settings.DATABASE_URL,
        pool_size=test_settings.DB_POOL_SIZE,
        max_overflow=test_settings.DB_MAX_OVERFLOW,
    )
    test_session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    app.state.settings = test_settings
    app.state.engine = test_engine
    app.state.session_factory = test_session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": SEED_ADMIN_EMAIL, "password": SEED_DEV_PASSWORD},
        )
    await test_engine.dispose()

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == SEED_ADMIN_EMAIL
    assert body["user"]["role"] == "admin"
    assert "password_hash" not in response.text


@pytest.mark.asyncio
async def test_seed_record_counts(seed_database: None, database_url: str) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await run_seed(session)
        await session.commit()

        user_count = await session.scalar(
            select(func.count()).select_from(User).where(User.email.like("%@ygip.test"))
        )
        pref_count = await session.scalar(select(func.count()).select_from(NotificationPreference))
        settings_count = await session.scalar(select(func.count()).select_from(SystemSetting))
        template_count = await session.scalar(select(func.count()).select_from(NewsletterTemplate))
        source_count = await session.scalar(select(func.count()).select_from(Source))

    await engine.dispose()

    assert user_count == 3
    assert pref_count == 3
    assert settings_count == 11
    assert template_count == 3
    assert source_count == 66
