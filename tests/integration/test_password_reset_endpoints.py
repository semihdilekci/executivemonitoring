"""Password reset endpoint integration testleri."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from apps.api.main import create_app
from apps.api.middleware.rate_limiter import InMemoryRateLimiterBackend
from apps.api.services.email_service import CapturingEmailService
from apps.api.services.password_reset_service import PasswordResetService
from httpx import AsyncClient
from packages.shared.models.audit_log import AuditLog
from packages.shared.models.password_reset_token import PasswordResetToken
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


@pytest.fixture
async def password_reset_client(
    test_settings,
    database_url: str,
) -> AsyncIterator[tuple[AsyncClient, CapturingEmailService]]:
    """Email capture ile API client."""
    capturing_mailer = CapturingEmailService()
    import apps.api.routers.auth as auth_router_module

    original_service = auth_router_module.password_reset_service
    auth_router_module.password_reset_service = PasswordResetService(mailer=capturing_mailer)

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

    from httpx import ASGITransport

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, capturing_mailer

    auth_router_module.password_reset_service = original_service
    await engine.dispose()


@pytest.fixture(autouse=True)
async def cleanup_password_reset_tokens(
    database_url: str,
) -> AsyncIterator[None]:
    yield
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(delete(PasswordResetToken))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_password_reset_full_flow(
    password_reset_client: tuple[AsyncClient, CapturingEmailService],
    admin_test_user: AuthTestUser,
    active_test_user: AuthTestUser,
    database_url: str,
) -> None:
    client, mailer = password_reset_client
    admin_token = await login_and_get_token(client, admin_test_user)

    initiate_response = await client.post(
        "/api/v1/auth/password-reset/initiate",
        headers=auth_headers(admin_token),
        json={"user_id": str(active_test_user.id)},
    )
    assert initiate_response.status_code == 200
    initiate_body = initiate_response.json()
    assert "e-posta" in initiate_body["message"]
    assert "expires_at" in initiate_body
    assert mailer.last_raw_token is not None
    assert mailer.last_email == active_test_user.email
    assert "token" not in initiate_response.text

    new_password = "ResetPass9"
    complete_response = await client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": mailer.last_raw_token, "new_password": new_password},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["message"] == "Şifre başarıyla güncellendi."

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": active_test_user.email, "password": active_test_user.password},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": active_test_user.email, "password": new_password},
    )
    assert new_login.status_code == 200

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        audit_result = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "password.reset_initiated",
                AuditLog.target_id == active_test_user.id,
            )
        )
        assert audit_result.scalar_one_or_none() is not None

        completed_result = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "password.reset_completed",
                AuditLog.target_id == active_test_user.id,
            )
        )
        assert completed_result.scalar_one_or_none() is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_complete_rejects_reused_token(
    password_reset_client: tuple[AsyncClient, CapturingEmailService],
    admin_test_user: AuthTestUser,
    active_test_user: AuthTestUser,
) -> None:
    client, mailer = password_reset_client
    admin_token = await login_and_get_token(client, admin_test_user)

    await client.post(
        "/api/v1/auth/password-reset/initiate",
        headers=auth_headers(admin_token),
        json={"user_id": str(active_test_user.id)},
    )
    assert mailer.last_raw_token is not None

    first = await client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": mailer.last_raw_token, "new_password": "FirstPass1"},
    )
    assert first.status_code == 200

    second = await client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": mailer.last_raw_token, "new_password": "SecondPass2"},
    )
    assert second.status_code == 401
    assert second.json()["error"]["code"] == "AUTH_INVALID_RESET_TOKEN"


@pytest.mark.asyncio
async def test_complete_rejects_invalid_token(password_reset_client) -> None:
    client, _ = password_reset_client
    response = await client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": "not-a-valid-token", "new_password": "ValidPass1"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_RESET_TOKEN"


@pytest.mark.asyncio
async def test_complete_rejects_weak_password(
    password_reset_client: tuple[AsyncClient, CapturingEmailService],
    admin_test_user: AuthTestUser,
    active_test_user: AuthTestUser,
) -> None:
    client, mailer = password_reset_client
    admin_token = await login_and_get_token(client, admin_test_user)
    await client.post(
        "/api/v1/auth/password-reset/initiate",
        headers=auth_headers(admin_token),
        json={"user_id": str(active_test_user.id)},
    )

    response = await client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": mailer.last_raw_token, "new_password": "alllowercase1"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PASSWORD_POLICY_VIOLATION"


@pytest.mark.asyncio
async def test_viewer_forbidden_on_initiate(
    password_reset_client: tuple[AsyncClient, CapturingEmailService],
    viewer_test_user: AuthTestUser,
    active_test_user: AuthTestUser,
) -> None:
    client, _ = password_reset_client
    token = await login_and_get_token(client, viewer_test_user)
    response = await client.post(
        "/api/v1/auth/password-reset/initiate",
        headers=auth_headers(token),
        json={"user_id": str(active_test_user.id)},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_initiate_unknown_user_returns_404(
    password_reset_client: tuple[AsyncClient, CapturingEmailService],
    admin_test_user: AuthTestUser,
) -> None:
    import uuid

    client, _ = password_reset_client
    admin_token = await login_and_get_token(client, admin_test_user)
    response = await client.post(
        "/api/v1/auth/password-reset/initiate",
        headers=auth_headers(admin_token),
        json={"user_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_complete_does_not_require_auth(password_reset_client) -> None:
    client, _ = password_reset_client
    response = await client.post(
        "/api/v1/auth/password-reset/complete",
        json={"token": "x", "new_password": "ValidPass1"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_RESET_TOKEN"
