"""Audit log endpoint integration testleri."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from packages.shared.models.audit_log import AuditLog
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


@pytest.mark.asyncio
async def test_admin_can_list_audit_logs(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get("/api/v1/audit-logs", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert "data" in body
    assert "pagination" in body
    assert isinstance(body["data"], list)


@pytest.mark.asyncio
async def test_viewer_forbidden_on_audit_logs(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.get("/api/v1/audit-logs", headers=auth_headers(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_audit_logs_filter_by_event_type(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    log_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            AuditLog(
                id=log_id,
                event_type="user.created",
                actor_user_id=admin_test_user.id,
                target_type="user",
                target_id=uuid.uuid4(),
                payload={"email": "filter-test@example.com", "role": "viewer"},
            )
        )
        await session.commit()

    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        "/api/v1/audit-logs",
        headers=auth_headers(token),
        params={"event_type": "user.created"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert any(item["id"] == str(log_id) for item in data)
    matched = next(item for item in data if item["id"] == str(log_id))
    assert matched["actor_name"] == "Admin Test User"
    assert matched["payload"]["email"] == "filter-test@example.com"
    assert "password" not in matched["payload"]

    async with session_factory() as session:
        await session.execute(delete(AuditLog).where(AuditLog.id == log_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_audit_logs_filter_by_actor_user_id(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    await api_client.post(
        "/api/v1/auth/logout",
        headers=auth_headers(token),
    )

    response = await api_client.get(
        "/api/v1/audit-logs",
        headers=auth_headers(token),
        params={"actor_user_id": str(admin_test_user.id), "event_type": "user.logout"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1
    assert all(item["actor_user_id"] == str(admin_test_user.id) for item in data)
    assert all(item["event_type"] == "user.logout" for item in data)


@pytest.mark.asyncio
async def test_audit_logs_unauthenticated_returns_401(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/audit-logs")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
