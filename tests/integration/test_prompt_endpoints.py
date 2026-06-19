"""Prompt template endpoint integration testleri."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from packages.shared.models.audit_log import AuditLog
from packages.shared.models.prompt_template import PromptTemplate
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


def _create_payload(*, name: str | None = None) -> dict[str, object]:
    unique = uuid.uuid4().hex[:8]
    return {
        "name": name or f"Test Template {unique}",
        "digest_type": "fmcg_weekly",
        "section_key": f"section_{unique}",
        "system_prompt": "Sen bir FMCG analisti olarak görev yapıyorsun.",
        "user_prompt_template": "Makaleler:\n{{ articles }}",
        "model_preference": "groq",
        "is_active": True,
    }


@pytest.fixture
async def created_template_id(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> AsyncIterator[uuid.UUID]:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.post(
        "/api/v1/prompt-templates",
        headers=auth_headers(token),
        json=_create_payload(),
    )
    assert response.status_code == 201
    template_id = uuid.UUID(response.json()["id"])

    yield template_id

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(delete(PromptTemplate).where(PromptTemplate.id == template_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_prompt_template_crud_and_audit(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    unique_suffix = uuid.uuid4().hex[:8]
    template_name = f"FMCG CRUD Template {unique_suffix}"
    payload = _create_payload(name=template_name)

    create_response = await api_client.post(
        "/api/v1/prompt-templates",
        headers=headers,
        json=payload,
    )
    assert create_response.status_code == 201
    created = create_response.json()
    template_id = created["id"]
    assert created["name"] == template_name
    assert created["digest_type"] == "fmcg_weekly"
    assert created["version"] == 1
    assert created["is_active"] is True

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        create_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "prompt_template.created",
                AuditLog.target_id == uuid.UUID(template_id),
            )
        )
        audit_row = create_audit.scalar_one_or_none()
        assert audit_row is not None
        assert "system_prompt" not in audit_row.payload
        assert "user_prompt_template" not in audit_row.payload

    list_response = await api_client.get("/api/v1/prompt-templates", headers=headers)
    assert list_response.status_code == 200
    listed = list_response.json()["data"]
    assert any(item["id"] == template_id for item in listed)

    detail_response = await api_client.get(
        f"/api/v1/prompt-templates/{template_id}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["section_key"] == payload["section_key"]

    update_payload = {
        **payload,
        "name": f"FMCG CRUD Template Updated {unique_suffix}",
        "user_prompt_template": "Güncel şablon:\n{{ articles }}",
        "is_active": False,
    }
    update_response = await api_client.put(
        f"/api/v1/prompt-templates/{template_id}",
        headers=headers,
        json=update_payload,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == f"FMCG CRUD Template Updated {unique_suffix}"
    assert updated["version"] == 2
    assert updated["is_active"] is False

    async with session_factory() as session:
        update_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "prompt_template.updated",
                AuditLog.target_id == uuid.UUID(template_id),
            )
        )
        assert update_audit.scalar_one_or_none() is not None
        await session.execute(
            delete(PromptTemplate).where(PromptTemplate.id == uuid.UUID(template_id))
        )
        await session.commit()

    await engine.dispose()


@pytest.mark.asyncio
async def test_viewer_forbidden_on_prompt_templates(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    list_response = await api_client.get("/api/v1/prompt-templates", headers=headers)
    assert list_response.status_code == 403
    assert list_response.json()["error"]["code"] == "FORBIDDEN"

    create_response = await api_client.post(
        "/api/v1/prompt-templates",
        headers=headers,
        json=_create_payload(),
    )
    assert create_response.status_code == 403


@pytest.mark.asyncio
async def test_create_prompt_template_invalid_digest_type_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    payload = _create_payload()
    payload["digest_type"] = "invalid_digest_type"

    response = await api_client.post(
        "/api/v1/prompt-templates",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_list_prompt_templates_filter_by_digest_type(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    created_template_id: uuid.UUID,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    filtered = await api_client.get(
        "/api/v1/prompt-templates",
        headers=headers,
        params={"digest_type": "fmcg_weekly"},
    )
    assert filtered.status_code == 200
    assert all(item["digest_type"] == "fmcg_weekly" for item in filtered.json()["data"])

    other = await api_client.get(
        "/api/v1/prompt-templates",
        headers=headers,
        params={"digest_type": "strategy_weekly"},
    )
    assert other.status_code == 200
    assert all(item["id"] != str(created_template_id) for item in other.json()["data"])
