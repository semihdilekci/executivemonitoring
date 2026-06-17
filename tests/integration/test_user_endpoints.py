"""Kullanıcı yönetimi endpoint integration testleri."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from packages.shared.models.audit_log import AuditLog
from packages.shared.models.notification_preference import NotificationPreference
from packages.shared.models.user import User
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


@pytest.fixture
async def created_user_id(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> AsyncIterator[uuid.UUID]:
    """Test sırasında oluşturulan kullanıcı — teardown ile silinir."""
    token = await login_and_get_token(api_client, admin_test_user)
    email = f"new-user-{uuid.uuid4()}@example.com"
    response = await api_client.post(
        "/api/v1/users",
        headers=auth_headers(token),
        json={
            "email": email,
            "full_name": "Yeni Kullanıcı",
            "role": "viewer",
            "password": "GeciciSifre1",
        },
    )
    assert response.status_code == 201
    user_id = uuid.UUID(response.json()["id"])

    yield user_id

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(delete(User).where(User.id == user_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_create_get_update_user(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    email = f"crud-{uuid.uuid4()}@example.com"

    create_response = await api_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": email,
            "full_name": "CRUD Test User",
            "role": "viewer",
            "password": "GeciciSifre1",
        },
    )
    assert create_response.status_code == 201
    created = create_response.json()
    user_id = created["id"]
    assert created["email"] == email
    assert created["role"] == "viewer"
    assert created["is_active"] is True
    assert "password_hash" not in create_response.text

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        pref = await session.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == uuid.UUID(user_id)
            )
        )
        assert pref.scalar_one_or_none() is not None

        audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "user.created",
                AuditLog.target_id == uuid.UUID(user_id),
            )
        )
        assert audit.scalar_one_or_none() is not None
    await engine.dispose()

    get_response = await api_client.get(f"/api/v1/users/{user_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["email"] == email

    update_response = await api_client.put(
        f"/api/v1/users/{user_id}",
        headers=headers,
        json={"full_name": "CRUD Updated", "role": "admin"},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["full_name"] == "CRUD Updated"
    assert updated["role"] == "admin"

    async with session_factory() as session:
        role_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "user.role_changed",
                AuditLog.target_id == uuid.UUID(user_id),
            )
        )
        assert role_audit.scalar_one_or_none() is not None
        await session.execute(delete(User).where(User.id == uuid.UUID(user_id)))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_users_pagination(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get("/api/v1/users", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "pagination" in body
    assert isinstance(body["data"], list)
    assert "has_more" in body["pagination"]


@pytest.mark.asyncio
async def test_get_users_me(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.get("/api/v1/users/me", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == viewer_test_user.email
    assert body["role"] == viewer_test_user.role.value
    assert "password_hash" not in response.text


@pytest.mark.asyncio
async def test_viewer_forbidden_on_admin_user_routes(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    list_response = await api_client.get("/api/v1/users", headers=headers)
    assert list_response.status_code == 403
    assert list_response.json()["error"]["code"] == "FORBIDDEN"

    create_response = await api_client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": f"denied-{uuid.uuid4()}@example.com",
            "full_name": "Denied",
            "role": "viewer",
            "password": "GeciciSifre1",
        },
    )
    assert create_response.status_code == 403

    get_response = await api_client.get(
        f"/api/v1/users/{admin_test_user.id}",
        headers=headers,
    )
    assert get_response.status_code == 403


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_email(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.post(
        "/api/v1/users",
        headers=auth_headers(token),
        json={
            "email": viewer_test_user.email,
            "full_name": "Duplicate",
            "role": "viewer",
            "password": "GeciciSifre1",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_EMAIL_EXISTS"


@pytest.mark.asyncio
async def test_create_user_rejects_weak_password(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.post(
        "/api/v1/users",
        headers=auth_headers(token),
        json={
            "email": f"weak-{uuid.uuid4()}@example.com",
            "full_name": "Weak Password",
            "role": "viewer",
            "password": "short",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PASSWORD_POLICY_VIOLATION"


@pytest.mark.asyncio
async def test_deactivate_user_writes_audit(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    created_user_id: uuid.UUID,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.put(
        f"/api/v1/users/{created_user_id}",
        headers=auth_headers(token),
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "user.deactivated",
                AuditLog.target_id == created_user_id,
            )
        )
        assert audit.scalar_one_or_none() is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_user_not_found(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        f"/api/v1/users/{uuid.uuid4()}",
        headers=auth_headers(token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
