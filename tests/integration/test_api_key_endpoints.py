"""API key yönetimi endpoint integration testleri."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from packages.shared.models.api_key import ApiKey
from packages.shared.models.api_usage_log import ApiUsageLog
from packages.shared.models.audit_log import AuditLog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


def _create_payload(*, alias: str | None = None) -> dict[str, object]:
    return {
        "provider": "groq",
        "key_alias": alias or f"Groq Test {uuid.uuid4()}",
        "api_key": "gsk_test_secret_key_value_1234567890",
        "priority_order": 1,
        "is_active": True,
    }


@pytest.fixture
async def created_api_key_id(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> AsyncIterator[uuid.UUID]:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.post(
        "/api/v1/api-keys",
        headers=auth_headers(token),
        json=_create_payload(),
    )
    assert response.status_code == 201
    key_id = uuid.UUID(response.json()["id"])

    yield key_id

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(delete(ApiKey).where(ApiKey.id == key_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_api_key_crud_and_audit(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    payload = _create_payload(alias="Groq Primary CRUD")

    create_response = await api_client.post("/api/v1/api-keys", headers=headers, json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    key_id = created["id"]
    assert created["provider"] == "groq"
    assert created["key_alias"] == "Groq Primary CRUD"
    assert created["is_active"] is True
    assert "api_key" not in created
    assert "encrypted_key" not in created
    assert payload["api_key"] not in create_response.text

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        create_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "api_key.created",
                AuditLog.target_id == uuid.UUID(key_id),
            )
        )
        audit_row = create_audit.scalar_one_or_none()
        assert audit_row is not None
        assert "api_key" not in audit_row.payload

        stored = await session.execute(select(ApiKey).where(ApiKey.id == uuid.UUID(key_id)))
        db_key = stored.scalar_one()
        assert db_key.encrypted_key.startswith("v1:")
        assert payload["api_key"] not in db_key.encrypted_key

    list_response = await api_client.get("/api/v1/api-keys", headers=headers)
    assert list_response.status_code == 200
    listed = list_response.json()["data"]
    assert any(item["id"] == key_id for item in listed)
    assert all("encrypted_key" not in item for item in listed)

    patch_response = await api_client.patch(
        f"/api/v1/api-keys/{key_id}/status",
        headers=headers,
        json={"is_active": False},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["is_active"] is False

    async with session_factory() as session:
        status_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "api_key.status_changed",
                AuditLog.target_id == uuid.UUID(key_id),
            )
        )
        assert status_audit.scalar_one_or_none() is not None

    delete_response = await api_client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
    assert delete_response.status_code == 200
    assert "silindi" in delete_response.json()["message"]

    async with session_factory() as session:
        delete_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "api_key.deleted",
                AuditLog.target_id == uuid.UUID(key_id),
            )
        )
        assert delete_audit.scalar_one_or_none() is not None
        remaining = await session.execute(select(ApiKey).where(ApiKey.id == uuid.UUID(key_id)))
        assert remaining.scalar_one_or_none() is None

    await engine.dispose()


@pytest.mark.asyncio
async def test_viewer_forbidden_on_api_keys(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    list_response = await api_client.get("/api/v1/api-keys", headers=headers)
    assert list_response.status_code == 403
    assert list_response.json()["error"]["code"] == "FORBIDDEN"

    create_response = await api_client.post(
        "/api/v1/api-keys",
        headers=headers,
        json=_create_payload(),
    )
    assert create_response.status_code == 403


@pytest.mark.asyncio
async def test_create_api_key_invalid_body_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/api-keys",
        headers=headers,
        json={
            "provider": "groq",
            "key_alias": "Bad",
            "api_key": "short",
            "priority_order": 1,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_delete_api_key_cascades_usage_logs(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    created_api_key_id: uuid.UUID,
    database_url: str,
) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            ApiUsageLog(
                api_key_id=created_api_key_id,
                provider="groq",
                model="groq/llama-3.1-70b-versatile",
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                request_type="chatbot",
                http_status=200,
                latency_ms=100,
            )
        )
        await session.commit()

    token = await login_and_get_token(api_client, admin_test_user)
    delete_response = await api_client.delete(
        f"/api/v1/api-keys/{created_api_key_id}",
        headers=auth_headers(token),
    )
    assert delete_response.status_code == 200

    async with session_factory() as session:
        usage_rows = await session.execute(
            select(ApiUsageLog).where(ApiUsageLog.api_key_id == created_api_key_id)
        )
        assert usage_rows.scalar_one_or_none() is None

    await engine.dispose()
