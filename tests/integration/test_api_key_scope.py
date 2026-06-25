"""API key `request_type_scope` create/update + audit integration testleri (`Docs/03` §6)."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from packages.shared.models.api_key import ApiKey
from packages.shared.models.audit_log import AuditLog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


def _payload(*, scope: list[str] | None = None) -> dict[str, object]:
    body: dict[str, object] = {
        "provider": "gemini",
        "key_alias": f"Gemini Scope {uuid.uuid4()}",
        "api_key": "AIza_test_secret_key_value_1234567890",
        "model": "gemini-2.5-flash-lite",
        "priority_order": 1,
        "is_active": True,
    }
    if scope is not None:
        body["request_type_scope"] = scope
    return body


async def _cleanup_key(database_url: str, key_id: uuid.UUID) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(delete(ApiKey).where(ApiKey.id == key_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_with_scope_and_default_empty(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    # Açık kapsam korunur.
    scoped = await api_client.post(
        "/api/v1/api-keys",
        headers=headers,
        json=_payload(scope=["article_translation"]),
    )
    assert scoped.status_code == 201
    scoped_body = scoped.json()
    assert scoped_body["request_type_scope"] == ["article_translation"]

    # Kapsam verilmezse `[]` (tüm operasyonlar).
    default = await api_client.post(
        "/api/v1/api-keys",
        headers=headers,
        json=_payload(),
    )
    assert default.status_code == 201
    assert default.json()["request_type_scope"] == []

    await _cleanup_key(database_url, uuid.UUID(scoped_body["id"]))
    await _cleanup_key(database_url, uuid.UUID(default.json()["id"]))


@pytest.mark.asyncio
async def test_update_scope_and_audit(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    created = await api_client.post(
        "/api/v1/api-keys",
        headers=headers,
        json=_payload(scope=["digest_generation"]),
    )
    assert created.status_code == 201
    key_id = created.json()["id"]

    patch = await api_client.patch(
        f"/api/v1/api-keys/{key_id}",
        headers=headers,
        json={
            "request_type_scope": ["article_translation", "chatbot"],
            "model": "gemini-2.5-flash",
        },
    )
    assert patch.status_code == 200
    patched = patch.json()
    assert patched["request_type_scope"] == ["article_translation", "chatbot"]
    assert patched["model"] == "gemini-2.5-flash"

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "api_key.updated",
                AuditLog.target_id == uuid.UUID(key_id),
            )
        )
        row = audit.scalar_one_or_none()
        assert row is not None
        assert row.payload["request_type_scope"] == ["article_translation", "chatbot"]
    await engine.dispose()

    await _cleanup_key(database_url, uuid.UUID(key_id))


@pytest.mark.asyncio
async def test_create_invalid_scope_value_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.post(
        "/api/v1/api-keys",
        headers=auth_headers(token),
        json=_payload(scope=["not_a_real_operation"]),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_update_invalid_model_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    created = await api_client.post(
        "/api/v1/api-keys",
        headers=headers,
        json=_payload(scope=["article_translation"]),
    )
    key_id = created.json()["id"]

    response = await api_client.patch(
        f"/api/v1/api-keys/{key_id}",
        headers=headers,
        json={"request_type_scope": [], "model": "claude-opus-4-8"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    await _cleanup_key(database_url, uuid.UUID(key_id))


@pytest.mark.asyncio
async def test_viewer_forbidden_on_scope_update(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    response = await api_client.patch(
        f"/api/v1/api-keys/{uuid.uuid4()}",
        headers=auth_headers(token),
        json={"request_type_scope": ["article_translation"]},
    )
    assert response.status_code == 403
