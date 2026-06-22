"""Pipeline run içerik kırılımı endpoint testleri (Faz 6.3).

`GET /api/v1/pipeline/runs/{id}/items` — run penceresindeki raw_items akıbet
sınıflandırması (`processed`/`filtered`/`failed`), kaynak kırılımı ve elenen içerik
listesi. Admin-only; viewer → 403. Gate ile elenen kayıt "Hatalı" değil "Elendi"
olarak görünür (`Docs/04` §8.3).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from packages.shared.enums import (
    PipelineRunStatus,
    PipelineRunType,
    RawItemStatus,
    SourceCategory,
    SourceStatus,
    SourceType,
)
from packages.shared.models.pipeline_run import PipelineRun
from packages.shared.models.processed_item import NewsProcessedItem
from packages.shared.models.raw_item import RawItem
from packages.shared.models.source import Source
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests.integration.conftest import (
    AuthTestUser,
    auth_headers,
    login_and_get_token,
)


@pytest.fixture
async def seeded_run(database_url: str) -> AsyncIterator[uuid.UUID]:
    """Pencerede 1 işlenen + 1 elenen + 1 hatalı raw_item taşıyan tamamlanmış run."""
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    # Uzak-gelecek pencere — test DB'sindeki mevcut raw_items'tan izole (paylaşımlı DB).
    now = datetime(2099, 1, 1, 12, 0, tzinfo=UTC)
    source_id = uuid.uuid4()
    run_id = uuid.uuid4()
    raw_ids = [uuid.uuid4() for _ in range(3)]

    async with session_factory() as session:
        session.add(
            Source(
                id=source_id,
                name=f"Test Feed {source_id.hex[:6]}",
                source_type=SourceType.RSS,
                config={"feed_url": "https://example.com/rss"},
                polling_interval_minutes=15,
                status=SourceStatus.ACTIVE,
                category=SourceCategory.FMCG,
                target_phase="mvp-0",
            )
        )
        session.add(
            PipelineRun(
                id=run_id,
                run_type=PipelineRunType.COLLECT_PIPELINE,
                status=PipelineRunStatus.COMPLETED,
                source_types=["rss"],
                params={},
                stats={},
                started_at=now - timedelta(hours=1),
                finished_at=now + timedelta(minutes=1),
            )
        )
        for index, raw_id in enumerate(raw_ids):
            session.add(
                RawItem(
                    id=raw_id,
                    source_id=source_id,
                    external_id=f"ext-{raw_id.hex[:8]}",
                    content_hash=f"sha256:{raw_id.hex}",
                    title=f"Haber {index}",
                    raw_content=f"İçerik gövdesi {index} " * 5,
                    raw_metadata={"url": f"https://example.com/{index}"},
                    fetched_at=now,
                    # 0 → işlenen (processed_item eklenir); 1 → elenen; 2 → hatalı.
                    status=(
                        RawItemStatus.FAILED if index == 2 else RawItemStatus.PROCESSED
                    ),
                )
            )
        # raw_items'ı önce flush et — processed_items FK'si bunlara bağlı (cross-schema
        # insert sıralaması garanti değil).
        await session.flush()
        # Yalnızca ilk kayıt processed_items'a yazılır → o "işlenen", diğeri "elenen".
        session.add(
            NewsProcessedItem(
                id=uuid.uuid4(),
                raw_item_id=raw_ids[0],
                source_id=source_id,
                title="Haber 0",
                clean_content="temiz içerik",
                language="tr",
                relevance_score=0.82,
                schema_category="news",
                content_category="macro",
                processed_at=now,
            )
        )
        await session.commit()

    yield run_id

    async with session_factory() as session:
        await session.execute(
            delete(NewsProcessedItem).where(
                NewsProcessedItem.raw_item_id.in_(raw_ids)
            )
        )
        await session.execute(delete(RawItem).where(RawItem.id.in_(raw_ids)))
        await session.execute(delete(PipelineRun).where(PipelineRun.id == run_id))
        await session.execute(delete(Source).where(Source.id == source_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_run_items_classifies_processed_filtered_failed(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    seeded_run: uuid.UUID,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.get(
        f"/api/v1/pipeline/runs/{seeded_run}/items", headers=headers
    )
    assert response.status_code == 200
    body = response.json()

    assert body["collected"] == 3
    assert body["processed"] == 1
    assert body["filtered"] == 1
    assert body["failed"] == 1
    assert body["total"] == 3
    assert len(body["items"]) == 3

    assert len(body["by_source"]) == 1
    src = body["by_source"][0]
    assert src["collected"] == 3
    assert src["processed"] == 1
    assert src["filtered"] == 1
    assert src["failed"] == 1


@pytest.mark.asyncio
async def test_run_items_outcome_filter_returns_only_filtered(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    seeded_run: uuid.UUID,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.get(
        f"/api/v1/pipeline/runs/{seeded_run}/items",
        params={"outcome": "filtered"},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()

    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["outcome"] == "filtered"
    # Elenen içerik gövdesi/başlığı görünür → editör keyword kararı verebilir.
    assert body["items"][0]["title"] == "Haber 1"
    assert body["items"][0]["snippet"]


@pytest.mark.asyncio
async def test_run_items_viewer_forbidden(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    seeded_run: uuid.UUID,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    response = await api_client.get(
        f"/api/v1/pipeline/runs/{seeded_run}/items", headers=headers
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_run_items_unknown_run_returns_404(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.get(
        f"/api/v1/pipeline/runs/{uuid.uuid4()}/items", headers=headers
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PIPELINE_RUN_NOT_FOUND"
