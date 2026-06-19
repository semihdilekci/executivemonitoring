"""Kaynak yönetimi endpoint integration testleri."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from packages.shared.enums import SourceStatus
from packages.shared.models.audit_log import AuditLog
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


def _valid_rss_payload(*, name: str | None = None) -> dict[str, object]:
    return {
        "name": name or f"Test RSS {uuid.uuid4()}",
        "source_type": "rss",
        "config": {
            "feed_url": "https://example.com/feed.xml",
            "ingest_mode": "filtered",
            "default_category": "turkish_media",
        },
        "polling_interval_minutes": 15,
        "category": "turkish_media",
        "target_phase": "mvp-0",
    }


@pytest.fixture
async def created_source_id(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> AsyncIterator[uuid.UUID]:
    """Test sırasında oluşturulan kaynak — teardown ile silinir."""
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.post(
        "/api/v1/sources",
        headers=auth_headers(token),
        json=_valid_rss_payload(),
    )
    assert response.status_code == 201
    source_id = uuid.UUID(response.json()["id"])

    yield source_id

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(delete(Source).where(Source.id == source_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_source_crud_and_audit(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    payload = _valid_rss_payload(name="CRUD Test RSS")

    create_response = await api_client.post("/api/v1/sources", headers=headers, json=payload)
    assert create_response.status_code == 201
    created = create_response.json()
    source_id = created["id"]
    assert created["name"] == "CRUD Test RSS"
    assert created["source_type"] == "rss"
    assert created["status"] == "active"
    assert created["config"]["feed_url"] == "https://example.com/feed.xml"

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "source.created",
                AuditLog.target_id == uuid.UUID(source_id),
            )
        )
        assert audit.scalar_one_or_none() is not None
    await engine.dispose()

    get_response = await api_client.get(f"/api/v1/sources/{source_id}", headers=headers)
    assert get_response.status_code == 200

    update_response = await api_client.put(
        f"/api/v1/sources/{source_id}",
        headers=headers,
        json={"name": "CRUD Updated RSS", "polling_interval_minutes": 30},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "CRUD Updated RSS"
    assert update_response.json()["polling_interval_minutes"] == 30

    status_response = await api_client.patch(
        f"/api/v1/sources/{source_id}/status",
        headers=headers,
        json={"status": "inactive"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "inactive"

    async with session_factory() as session:
        status_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "source.status_changed",
                AuditLog.target_id == uuid.UUID(source_id),
            )
        )
        assert status_audit.scalar_one_or_none() is not None

    delete_response = await api_client.delete(f"/api/v1/sources/{source_id}", headers=headers)
    assert delete_response.status_code == 200
    body = delete_response.json()
    assert body["deleted_raw_items_count"] == 0
    assert "silindi" in body["message"]

    async with session_factory() as session:
        delete_audit = await session.execute(
            select(AuditLog).where(
                AuditLog.event_type == "source.deleted",
                AuditLog.target_id == uuid.UUID(source_id),
            )
        )
        assert delete_audit.scalar_one_or_none() is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_viewer_forbidden_on_sources(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    list_response = await api_client.get("/api/v1/sources", headers=headers)
    assert list_response.status_code == 403
    assert list_response.json()["error"]["code"] == "FORBIDDEN"

    create_response = await api_client.post(
        "/api/v1/sources",
        headers=headers,
        json=_valid_rss_payload(),
    )
    assert create_response.status_code == 403


@pytest.mark.asyncio
async def test_create_source_invalid_config_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    payload = _valid_rss_payload()
    payload["config"] = {"ingest_mode": "invalid", "default_category": "fmcg"}

    response = await api_client.post("/api/v1/sources", headers=headers, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_create_source_missing_feed_url_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    payload = _valid_rss_payload()
    payload["config"] = {
        "ingest_mode": "all",
        "default_category": "fmcg",
    }

    response = await api_client.post("/api/v1/sources", headers=headers, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_error_to_active_resets_error_count(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
    created_source_id: uuid.UUID,
) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        source = await session.get(Source, created_source_id)
        assert source is not None
        source.status = SourceStatus.ERROR
        source.error_count = 3
        await session.commit()

    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.patch(
        f"/api/v1/sources/{created_source_id}/status",
        headers=auth_headers(token),
        json={"status": "active"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["error_count"] == 0
    await engine.dispose()


@pytest.mark.asyncio
async def test_delete_source_returns_raw_items_count(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
    created_source_id: uuid.UUID,
) -> None:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        session.add(
            RawItem(
                source_id=created_source_id,
                external_id="ext-1",
                content_hash="a" * 64,
                raw_content="test content",
            )
        )
        await session.commit()

    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.delete(
        f"/api/v1/sources/{created_source_id}",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["deleted_raw_items_count"] == 1
    await engine.dispose()
