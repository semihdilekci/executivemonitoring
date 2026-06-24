"""İçerik Arşivi API integration testleri (Faz 6.2 — İterasyon 3).

Admin-only liste + detay endpoint'leri; RBAC deny (viewer 403), `news` schema
lookup, `404 PROCESSED_ITEM_NOT_FOUND`, varsayılan `schema_category=news` (Faz 6.4).
Seed: 1 source → 1 raw_item → 1 news.processed_item + 2 content_chunk + 1 digest
section reverse-reference.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pytest
from httpx import AsyncClient
from packages.shared.enums import (
    DigestStatus,
    DigestType,
    RawItemStatus,
    SourceCategory,
    SourceStatus,
    SourceType,
)
from packages.shared.models.content_chunk import EMBEDDING_DIMENSION, ContentChunk
from packages.shared.models.digest import Digest
from packages.shared.models.digest_section import DigestSection
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


@dataclass(frozen=True)
class ArchiveSeed:
    """Seed edilen arşiv kaydının test sabitleri."""

    source_id: uuid.UUID
    raw_item_id: uuid.UUID
    item_id: uuid.UUID
    digest_id: uuid.UUID
    section_title: str
    schema_category: str = "news"


@pytest.fixture
async def archive_seed(database_url: str) -> AsyncIterator[ArchiveSeed]:
    """Tek news.processed_item + bülten reverse-reference seed eder; teardown temizler."""
    source_id = uuid.uuid4()
    raw_item_id = uuid.uuid4()
    item_id = uuid.uuid4()
    digest_id = uuid.uuid4()
    section_title = "Makroekonomik Gelişmeler"

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Source(
                id=source_id,
                name=f"Content Archive {source_id}",
                source_type=SourceType.RSS,
                config={"feed_url": "https://example.com/feed.xml"},
                polling_interval_minutes=15,
                status=SourceStatus.ACTIVE,
                category=SourceCategory.STRATEGY,
                target_phase="mvp-0",
            )
        )
        session.add(
            RawItem(
                id=raw_item_id,
                source_id=source_id,
                external_id="https://example.com/article/archive",
                content_hash="a" * 64,
                title="TCMB faiz kararı",
                raw_content="ham içerik",
                status=RawItemStatus.PROCESSED,
            )
        )
        # Cross-schema FK (news.processed_items → public.raw_items) — parent satırlar
        # önce commit edilmeli; SQLAlchemy UoW şema sınırı ötesinde sıra garanti etmez.
        await session.commit()

    async with session_factory() as session:
        session.add(
            NewsProcessedItem(
                id=item_id,
                raw_item_id=raw_item_id,
                source_id=source_id,
                title="TCMB faiz kararı piyasaları hareketlendirdi",
                clean_content="Tam normalize edilmiş metin gövdesi.",
                summary="Kısa özet.",
                language="tr",
                relevance_score=0.82,
                topics=["tcmb", "faiz", "enflasyon"],
                entities=[{"type": "ORG", "value": "TCMB"}],
                published_at=datetime(2026, 6, 18, 9, 30, tzinfo=UTC),
                processed_at=datetime(2026, 6, 18, 9, 31, tzinfo=UTC),
                schema_category="news",
                content_category="macro",
            )
        )
        # Cross-schema FK (public.content_chunks → news.processed_items) — parent
        # önce flush edilmeli; UoW şema sınırı ötesinde sıra garanti etmez (Faz 6.4).
        await session.flush()
        for idx in range(2):
            session.add(
                ContentChunk(
                    processed_item_id=item_id,
                    chunk_index=idx,
                    chunk_text=f"parça {idx}",
                    token_count=10,
                    embedding=[0.0] * EMBEDDING_DIMENSION,
                )
            )
        session.add(
            Digest(
                id=digest_id,
                digest_type=DigestType.STRATEGY_WEEKLY,
                title="Strateji Haftalık — 9–15 Haziran 2026",
                status=DigestStatus.READY,
                period_start=date(2026, 6, 9),
                period_end=date(2026, 6, 15),
            )
        )
        session.add(
            DigestSection(
                digest_id=digest_id,
                section_order=0,
                section_title=section_title,
                ai_summary="Bölüm özeti.",
                source_references=[{"processed_item_id": str(item_id), "title": "TCMB"}],
            )
        )
        await session.commit()

    yield ArchiveSeed(
        source_id=source_id,
        raw_item_id=raw_item_id,
        item_id=item_id,
        digest_id=digest_id,
        section_title=section_title,
    )

    async with session_factory() as session:
        await session.execute(delete(DigestSection).where(DigestSection.digest_id == digest_id))
        await session.execute(delete(Digest).where(Digest.id == digest_id))
        await session.execute(
            delete(ContentChunk).where(ContentChunk.processed_item_id == item_id)
        )
        await session.execute(delete(NewsProcessedItem).where(NewsProcessedItem.id == item_id))
        await session.execute(delete(RawItem).where(RawItem.id == raw_item_id))
        await session.execute(delete(Source).where(Source.id == source_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_admin_lists_archive_returns_seeded_item(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    archive_seed: ArchiveSeed,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        "/api/v1/admin/processed-items",
        headers=auth_headers(token),
        params={"schema_category": "news", "source_id": str(archive_seed.source_id)},
    )

    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body["data"]]
    assert str(archive_seed.item_id) in ids
    item = next(i for i in body["data"] if i["id"] == str(archive_seed.item_id))
    assert "clean_content" not in item  # liste yanıtında tam metin yok
    assert item["schema_category"] == "news"
    assert any(u["digest_id"] == str(archive_seed.digest_id) for u in item["digest_usages"])


@pytest.mark.asyncio
async def test_has_digest_filter_is_db_level_not_sort_dependent(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    archive_seed: ArchiveSeed,
) -> None:
    """has_digest DB seviyesinde filtrelenir — sıralamadan bağımsız çalışmalı.

    Regresyon: önceden has_digest pagination sonrası servis katmanında
    filtreleniyordu; varsayılan `processed_at desc` sıralamasında bülten kullanan
    içerikler ilk sayfaya düşmeyip sonuç boş görünüyordu (`has_digest=true`).
    Seed edilen tek içerik bir bültende kullanılıyor.
    """
    token = await login_and_get_token(api_client, admin_test_user)
    base = {"schema_category": "news", "source_id": str(archive_seed.source_id)}

    # Varsayılan sıralama (sort param yok) + has_digest=true → içerik gelmeli.
    used_default = await api_client.get(
        "/api/v1/admin/processed-items",
        headers=auth_headers(token),
        params={**base, "has_digest": "true"},
    )
    assert used_default.status_code == 200
    used_ids = [i["id"] for i in used_default.json()["data"]]
    assert str(archive_seed.item_id) in used_ids

    # Açık sıralama ile de aynı sonuç (eski hatada yalnızca bu çalışıyordu).
    used_sorted = await api_client.get(
        "/api/v1/admin/processed-items",
        headers=auth_headers(token),
        params={**base, "has_digest": "true", "sort_by": "relevance_score"},
    )
    assert used_sorted.status_code == 200
    assert str(archive_seed.item_id) in [i["id"] for i in used_sorted.json()["data"]]

    # has_digest=false → bülten kullanan tek seed içerik hariç tutulmalı.
    unused = await api_client.get(
        "/api/v1/admin/processed-items",
        headers=auth_headers(token),
        params={**base, "has_digest": "false"},
    )
    assert unused.status_code == 200
    assert str(archive_seed.item_id) not in [i["id"] for i in unused.json()["data"]]


@pytest.mark.asyncio
async def test_admin_detail_returns_full_content_and_usages(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    archive_seed: ArchiveSeed,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        f"/api/v1/admin/processed-items/{archive_seed.item_id}",
        headers=auth_headers(token),
        params={"schema_category": "news"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(archive_seed.item_id)
    assert body["clean_content"] == "Tam normalize edilmiş metin gövdesi."
    assert body["entities"] == [{"type": "ORG", "value": "TCMB"}]
    assert body["chunk_count"] == 2
    assert len(body["digest_usages"]) == 1
    usage = body["digest_usages"][0]
    assert usage["digest_id"] == str(archive_seed.digest_id)
    assert usage["section_title"] == archive_seed.section_title


@pytest.mark.asyncio
async def test_detail_wrong_schema_returns_404(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    archive_seed: ArchiveSeed,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        f"/api/v1/admin/processed-items/{archive_seed.item_id}",
        headers=auth_headers(token),
        params={"schema_category": "market"},  # kayıt news şemasında
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROCESSED_ITEM_NOT_FOUND"


@pytest.mark.asyncio
async def test_detail_defaults_to_news_schema(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    archive_seed: ArchiveSeed,
) -> None:
    """schema_category verilmezse varsayılan `news` (Faz 6.4) — kayıt bulunur."""
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        f"/api/v1/admin/processed-items/{archive_seed.item_id}",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(archive_seed.item_id)
    assert body["schema_category"] == "news"


@pytest.mark.asyncio
async def test_viewer_denied_on_list_and_detail(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    archive_seed: ArchiveSeed,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    list_response = await api_client.get("/api/v1/admin/processed-items", headers=headers)
    assert list_response.status_code == 403

    detail_response = await api_client.get(
        f"/api/v1/admin/processed-items/{archive_seed.item_id}",
        headers=headers,
        params={"schema_category": "news"},
    )
    assert detail_response.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_denied(
    api_client: AsyncClient,
    archive_seed: ArchiveSeed,
) -> None:
    response = await api_client.get(
        f"/api/v1/admin/processed-items/{archive_seed.item_id}",
        params={"schema_category": "news"},
    )
    assert response.status_code == 401
