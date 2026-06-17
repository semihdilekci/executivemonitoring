"""Auth endpoint integration testleri."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from packages.shared.models.audit_log import AuditLog
from packages.shared.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import AuthTestUser


@pytest.mark.asyncio
async def test_login_refresh_logout_happy_path(
    api_client: AsyncClient,
    active_test_user: AuthTestUser,
    database_url: str,
) -> None:
    login_response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": active_test_user.email, "password": active_test_user.password},
    )
    assert login_response.status_code == 200
    login_body = login_response.json()
    assert "access_token" in login_body
    assert "refresh_token" in login_body
    assert login_body["token_type"] == "bearer"
    assert login_body["expires_in"] == 3600
    assert login_body["user"]["email"] == active_test_user.email
    assert login_body["user"]["role"] == active_test_user.role.value
    assert "password_hash" not in login_response.text

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        user_result = await session.execute(select(User).where(User.id == active_test_user.id))
        user = user_result.scalar_one()
        assert user.last_login_at is not None

        audit_result = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "user.login",
                AuditLog.actor_user_id == active_test_user.id,
            )
        )
        assert audit_result.scalar_one_or_none() is not None
    await engine.dispose()

    refresh_response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login_body["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refresh_body = refresh_response.json()
    assert "access_token" in refresh_body
    assert "refresh_token" not in refresh_body
    assert refresh_body["expires_in"] == 3600

    logout_response = await api_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {refresh_body['access_token']}"},
    )
    assert logout_response.status_code == 200
    assert logout_response.json() == {"message": "Oturum sonlandırıldı."}

    async with session_factory() as session:
        logout_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "user.logout",
                AuditLog.actor_user_id == active_test_user.id,
            )
        )
        assert logout_audit.scalar_one_or_none() is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(
    api_client: AsyncClient,
    active_test_user: AuthTestUser,
    database_url: str,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": active_test_user.email, "password": "WrongPass1"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        audit_result = await session.execute(
            select(AuditLog).where(AuditLog.event_type == "user.login_failed")
        )
        failed_logs = audit_result.scalars().all()
        assert any(
            log.payload.get("email_attempted") == active_test_user.email for log in failed_logs
        )
    await engine.dispose()


@pytest.mark.asyncio
async def test_login_rejects_unknown_email(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "TestPass1"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_rejects_inactive_user(
    api_client: AsyncClient,
    inactive_test_user: AuthTestUser,
) -> None:
    response = await api_client.post(
        "/api/v1/auth/login",
        json={"email": inactive_test_user.email, "password": inactive_test_user.password},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_refresh_rejects_invalid_token(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not-a-valid-token"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_INVALID_REFRESH_TOKEN"


@pytest.mark.asyncio
async def test_refresh_rejects_inactive_user(
    api_client: AsyncClient,
    inactive_test_user: AuthTestUser,
) -> None:
    from apps.api.core.config import get_settings
    from apps.api.core.security import create_refresh_token

    refresh_token = create_refresh_token(
        str(inactive_test_user.id),
        settings=get_settings(),
    )
    response = await api_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_ACCOUNT_INACTIVE"


@pytest.mark.asyncio
async def test_logout_requires_authentication(api_client: AsyncClient) -> None:
    response = await api_client.post("/api/v1/auth/logout")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_login_rate_limit_exceeded(
    api_client: AsyncClient,
    active_test_user: AuthTestUser,
) -> None:
    last_status = 200
    for _ in range(11):
        response = await api_client.post(
            "/api/v1/auth/login",
            json={"email": active_test_user.email, "password": "WrongPass1"},
        )
        last_status = response.status_code

    assert last_status == 429
    assert response.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in response.headers
