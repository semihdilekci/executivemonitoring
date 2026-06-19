"""Digest endpoint integration testleri."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from apps.api.services.digest_service import digest_service
from httpx import AsyncClient
from packages.shared.enums import DigestStatus, DigestType
from packages.shared.models.digest import Digest
from packages.shared.models.digest_section import DigestSection
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


async def _noop_scheduler(**_kwargs: Any) -> None:
    return None


@pytest.fixture(autouse=True)
def _patch_digest_generation_scheduler() -> AsyncIterator[None]:
    original_scheduler = digest_service._generation_scheduler
    digest_service._generation_scheduler = _noop_scheduler
    yield
    digest_service._generation_scheduler = original_scheduler


@pytest.fixture
async def ready_digest_id(database_url: str) -> AsyncIterator[uuid.UUID]:
    digest_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Digest(
                id=digest_id,
                digest_type=DigestType.FMCG_WEEKLY,
                title="FMCG Haftalık Bülten — 9-15 Haziran 2026",
                status=DigestStatus.READY,
                period_start=date(2026, 6, 9),
                period_end=date(2026, 6, 15),
                total_sources_used=3,
                completed_at=datetime(2026, 6, 15, 10, 5, 32, tzinfo=UTC),
            )
        )
        session.add(
            DigestSection(
                digest_id=digest_id,
                section_order=1,
                section_title="Piyasa Özeti",
                ai_summary="Bu hafta FMCG piyasasında hareketlilik arttı.",
                impact_note="Olumlu sinyaller.",
                source_references=[
                    {
                        "processed_item_id": str(uuid.uuid4()),
                        "title": "Örnek Haber",
                        "url": "https://example.com/article",
                    }
                ],
            )
        )
        await session.commit()

    yield digest_id

    async with session_factory() as session:
        await session.execute(delete(DigestSection).where(DigestSection.digest_id == digest_id))
        await session.execute(delete(Digest).where(Digest.id == digest_id))
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def generating_digest_id(database_url: str) -> AsyncIterator[uuid.UUID]:
    digest_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Digest(
                id=digest_id,
                digest_type=DigestType.STRATEGY_WEEKLY,
                title="Strateji Haftalık Bülten — 1-7 Haziran 2026",
                status=DigestStatus.GENERATING,
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 7),
                total_sources_used=0,
            )
        )
        await session.commit()

    yield digest_id

    async with session_factory() as session:
        await session.execute(delete(Digest).where(Digest.id == digest_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_list_and_detail_ready_digest(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    ready_digest_id: uuid.UUID,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    list_response = await api_client.get("/api/v1/digests", headers=headers)
    assert list_response.status_code == 200
    listed = list_response.json()["data"]
    assert any(item["id"] == str(ready_digest_id) for item in listed)
    assert all(item["status"] == "ready" for item in listed)

    detail_response = await api_client.get(
        f"/api/v1/digests/{ready_digest_id}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "ready"
    assert len(detail["sections"]) == 1
    assert detail["sections"][0]["section_title"] == "Piyasa Özeti"
    assert detail["sections"][0]["source_references"][0]["title"] == "Örnek Haber"


@pytest.mark.asyncio
async def test_viewer_cannot_see_non_ready_digest(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    generating_digest_id: uuid.UUID,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    detail_response = await api_client.get(
        f"/api/v1/digests/{generating_digest_id}",
        headers=headers,
    )
    assert detail_response.status_code == 404
    assert detail_response.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_viewer_cannot_filter_non_ready_status(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    response = await api_client.get(
        "/api/v1/digests",
        headers=headers,
        params={"status": "generating"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_generate_digest(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    payload = {
        "digest_type": "fmcg_weekly",
        "period_start": "2026-07-01",
        "period_end": "2026-07-07",
    }

    response = await api_client.post(
        "/api/v1/digests/generate",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "generating"
    assert body["message"] == "Bülten üretimi başlatıldı."
    digest_id = uuid.UUID(body["id"])

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        digest = await session.get(Digest, digest_id)
        assert digest is not None
        assert digest.status == DigestStatus.GENERATING
        await session.execute(delete(DigestSection).where(DigestSection.digest_id == digest_id))
        await session.execute(delete(Digest).where(Digest.id == digest_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_viewer_cannot_generate_digest(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/digests/generate",
        headers=headers,
        json={
            "digest_type": "fmcg_weekly",
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_admin_can_list_generating_digest(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    generating_digest_id: uuid.UUID,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.get(
        "/api/v1/digests",
        headers=headers,
        params={"status": "generating"},
    )
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["data"]]
    assert str(generating_digest_id) in ids


@pytest.mark.asyncio
async def test_generate_invalid_period_returns_422(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/digests/generate",
        headers=headers,
        json={
            "digest_type": "fmcg_weekly",
            "period_start": "2026-07-10",
            "period_end": "2026-07-01",
        },
    )
    assert response.status_code == 422
