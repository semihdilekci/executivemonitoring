"""İçerik arşivi detayında `translations` (TR/EN) integration testleri (`Docs/03` §11.6)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from packages.shared.enums import (
    RawItemStatus,
    SourceCategory,
    SourceStatus,
    SourceType,
)
from packages.shared.models.processed_item import NewsProcessedItem
from packages.shared.models.processed_item_translation import ProcessedItemTranslation
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
class TranslationSeed:
    source_id: uuid.UUID
    raw_translated_id: uuid.UUID
    translated_item_id: uuid.UUID
    raw_tr_id: uuid.UUID
    tr_only_item_id: uuid.UUID


def _raw_item(raw_id: uuid.UUID, source_id: uuid.UUID, suffix: str) -> RawItem:
    return RawItem(
        id=raw_id,
        source_id=source_id,
        external_id=f"https://example.com/article/{suffix}",
        content_hash=suffix * 8,
        title="x",
        raw_content="ham",
        status=RawItemStatus.PROCESSED,
    )


@pytest.fixture
async def translation_seed(database_url: str) -> AsyncIterator[TranslationSeed]:
    source_id = uuid.uuid4()
    raw_translated_id = uuid.uuid4()
    translated_item_id = uuid.uuid4()
    raw_tr_id = uuid.uuid4()
    tr_only_item_id = uuid.uuid4()

    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Source(
                id=source_id,
                name=f"Translation Archive {source_id}",
                source_type=SourceType.RSS,
                config={"feed_url": "https://example.com/feed.xml"},
                polling_interval_minutes=15,
                status=SourceStatus.ACTIVE,
                category=SourceCategory.STRATEGY,
                target_phase="mvp-0",
            )
        )
        session.add(_raw_item(raw_translated_id, source_id, "aaaaaaaa"))
        session.add(_raw_item(raw_tr_id, source_id, "bbbbbbbb"))
        await session.commit()

    async with session_factory() as session:
        # Çevrilmiş (canonical TR + orijinal EN satırı) haber.
        session.add(
            NewsProcessedItem(
                id=translated_item_id,
                raw_item_id=raw_translated_id,
                source_id=source_id,
                title="Merkez bankası faiz kararını açıkladı",
                clean_content="Canonical Türkçe içerik.",
                language="tr",
                relevance_score=0.9,
                topics=[],
                entities=[],
                published_at=datetime(2026, 6, 18, 9, 30, tzinfo=UTC),
                processed_at=datetime(2026, 6, 18, 9, 31, tzinfo=UTC),
                schema_category="news",
                content_category="macro",
            )
        )
        # TR kaynaklı (çeviri yok) haber.
        session.add(
            NewsProcessedItem(
                id=tr_only_item_id,
                raw_item_id=raw_tr_id,
                source_id=source_id,
                title="Yerli haber",
                clean_content="Türkçe kaynak içeriği.",
                language="tr",
                relevance_score=0.5,
                topics=[],
                entities=[],
                published_at=datetime(2026, 6, 18, 9, 30, tzinfo=UTC),
                processed_at=datetime(2026, 6, 18, 9, 31, tzinfo=UTC),
                schema_category="news",
                content_category="macro",
            )
        )
        await session.flush()
        session.add(
            ProcessedItemTranslation(
                processed_item_id=translated_item_id,
                language="en",
                title="Central bank announces interest rate decision",
                content="Original English content.",
                is_original=True,
            )
        )
        await session.commit()

    yield TranslationSeed(
        source_id=source_id,
        raw_translated_id=raw_translated_id,
        translated_item_id=translated_item_id,
        raw_tr_id=raw_tr_id,
        tr_only_item_id=tr_only_item_id,
    )

    async with session_factory() as session:
        for item_id in (translated_item_id, tr_only_item_id):
            await session.execute(
                delete(NewsProcessedItem).where(NewsProcessedItem.id == item_id)
            )
        await session.execute(
            delete(RawItem).where(RawItem.source_id == source_id)
        )
        await session.execute(delete(Source).where(Source.id == source_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_detail_returns_original_english_translation(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    translation_seed: TranslationSeed,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        f"/api/v1/admin/processed-items/{translation_seed.translated_item_id}",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "tr"
    assert body["clean_content"] == "Canonical Türkçe içerik."
    assert len(body["translations"]) == 1
    variant = body["translations"][0]
    assert variant["language"] == "en"
    assert variant["is_original"] is True
    assert variant["title"] == "Central bank announces interest rate decision"
    assert variant["content"] == "Original English content."


@pytest.mark.asyncio
async def test_detail_tr_only_returns_empty_translations(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    translation_seed: TranslationSeed,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    response = await api_client.get(
        f"/api/v1/admin/processed-items/{translation_seed.tr_only_item_id}",
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["translations"] == []
