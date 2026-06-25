"""Digest endpoint integration testleri (Faz 6.5 — ADR-0003).

`digest_type` → `newsletter_slug`; üretim `newsletter_template_id` ile tetiklenir;
anlık etki (`news-impact`) endpoint'i (404 / admin 200 / viewer 200).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
from apps.api.services.digest_service import digest_service
from httpx import AsyncClient
from packages.shared.enums import (
    DigestStatus,
    RawItemStatus,
    SourceCategory,
    SourceStatus,
    SourceType,
)
from packages.shared.models.digest import Digest
from packages.shared.models.digest_section import DigestSection
from packages.shared.models.newsletter_template import NewsletterSection, NewsletterTemplate
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


async def _noop_scheduler(**_kwargs: Any) -> None:
    return None


@pytest.fixture(autouse=True)
def _patch_digest_generation_scheduler() -> AsyncIterator[None]:
    original_scheduler = digest_service._generation_scheduler
    digest_service._generation_scheduler = _noop_scheduler
    yield
    digest_service._generation_scheduler = original_scheduler


class _FakeLLMResponse:
    def __init__(self, text: str) -> None:
        self.text = text


class _FakeLLMClient:
    """`complete()` çağrısını sabit metinle karşılayan stub (gerçek LLM yok)."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[str] = []

    async def complete(self, prompt: str, **_kwargs: Any) -> _FakeLLMResponse:
        self.calls.append(prompt)
        return _FakeLLMResponse(self._text)


@pytest.fixture
def fake_llm_client() -> AsyncIterator[_FakeLLMClient]:
    client = _FakeLLMClient("Mondelez yeniden yapılanması Yıldız için fırsat.")
    original = digest_service._llm_client_factory

    async def factory(_db: AsyncSession) -> Any:
        return client

    digest_service._llm_client_factory = factory  # type: ignore[assignment]
    yield client
    digest_service._llm_client_factory = original


@pytest.fixture
async def ready_digest_id(database_url: str) -> AsyncIterator[uuid.UUID]:
    digest_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Digest(
                id=digest_id,
                newsletter_slug="fmcg_weekly",
                title="FMCG Haftalık Bülten — 9-15 Haziran 2026",
                summary="Bu hafta kakao fiyatları ve AB ambalaj direktifi öne çıktı.",
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
                newsletter_slug="strategy_weekly",
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


@pytest.fixture
async def newsletter_template_id(database_url: str) -> AsyncIterator[uuid.UUID]:
    template_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            NewsletterTemplate(
                id=template_id,
                slug=f"test_news_{template_id.hex[:8]}",
                name="Test Bülteni",
                description="Test",
                date_range_days=7,
                summary_system_prompt="Sistem",
                summary_user_prompt="Bölümler: {sections}\nHaberler: {articles}",
                min_content_score=50,
                sections=[
                    NewsletterSection(
                        name="Genel",
                        sort_order=0,
                        section_system_prompt="Sistem",
                        section_user_prompt="Haberler: {articles}",
                        impact_prompt="Etki?",
                    )
                ],
            )
        )
        await session.commit()

    yield template_id

    async with session_factory() as session:
        await session.execute(
            delete(Digest).where(Digest.newsletter_template_id == template_id)
        )
        await session.execute(
            delete(NewsletterTemplate).where(NewsletterTemplate.id == template_id)
        )
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def news_item_id(database_url: str) -> AsyncIterator[uuid.UUID]:
    source_id = uuid.uuid4()
    raw_item_id = uuid.uuid4()
    item_id = uuid.uuid4()
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        session.add(
            Source(
                id=source_id,
                name=f"News Impact {source_id}",
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
                external_id="https://example.com/article/impact",
                content_hash="b" * 64,
                title="Mondelez yeniden yapılanma",
                raw_content="ham içerik",
                status=RawItemStatus.PROCESSED,
            )
        )
        await session.commit()

    async with session_factory() as session:
        session.add(
            NewsProcessedItem(
                id=item_id,
                raw_item_id=raw_item_id,
                source_id=source_id,
                title="Mondelez yeniden yapılanmaya gidiyor",
                clean_content="Mondelez global operasyonlarını yeniden yapılandırıyor.",
                summary="Kısa özet.",
                language="tr",
                relevance_score=0.78,
                topics=["mondelez", "fmcg"],
                entities=[{"type": "ORG", "value": "Mondelez"}],
                published_at=datetime(2026, 6, 18, 9, 30, tzinfo=UTC),
                processed_at=datetime(2026, 6, 18, 9, 31, tzinfo=UTC),
                schema_category="news",
                content_category="fmcg",
            )
        )
        await session.commit()

    yield item_id

    async with session_factory() as session:
        await session.execute(delete(NewsProcessedItem).where(NewsProcessedItem.id == item_id))
        await session.execute(delete(RawItem).where(RawItem.id == raw_item_id))
        await session.execute(delete(Source).where(Source.id == source_id))
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
    target = next(item for item in listed if item["id"] == str(ready_digest_id))
    assert target["newsletter_slug"] == "fmcg_weekly"

    detail_response = await api_client.get(
        f"/api/v1/digests/{ready_digest_id}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["status"] == "ready"
    assert detail["summary"].startswith("Bu hafta kakao")
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
    newsletter_template_id: uuid.UUID,
    database_url: str,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)
    payload = {
        "newsletter_template_id": str(newsletter_template_id),
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
        assert digest.newsletter_template_id == newsletter_template_id
        await session.execute(delete(DigestSection).where(DigestSection.digest_id == digest_id))
        await session.execute(delete(Digest).where(Digest.id == digest_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_generate_unknown_template_returns_404(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/digests/generate",
        headers=headers,
        json={
            "newsletter_template_id": str(uuid.uuid4()),
            "period_start": "2026-07-01",
            "period_end": "2026-07-07",
        },
    )
    assert response.status_code == 404


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
            "newsletter_template_id": str(uuid.uuid4()),
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
            "newsletter_template_id": str(uuid.uuid4()),
            "period_start": "2026-07-10",
            "period_end": "2026-07-01",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_news_impact_returns_analysis(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    news_item_id: uuid.UUID,
    fake_llm_client: _FakeLLMClient,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/digests/news-impact",
        headers=headers,
        json={"processed_item_id": str(news_item_id)},
    )
    assert response.status_code == 200
    assert response.json()["analysis"].startswith("Mondelez")
    assert fake_llm_client.calls  # LLM çağrıldı


@pytest.mark.asyncio
async def test_viewer_can_news_impact(
    api_client: AsyncClient,
    viewer_test_user: AuthTestUser,
    news_item_id: uuid.UUID,
    fake_llm_client: _FakeLLMClient,
) -> None:
    token = await login_and_get_token(api_client, viewer_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/digests/news-impact",
        headers=headers,
        json={"processed_item_id": str(news_item_id)},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_news_impact_unknown_item_returns_404(
    api_client: AsyncClient,
    admin_test_user: AuthTestUser,
    fake_llm_client: _FakeLLMClient,
) -> None:
    token = await login_and_get_token(api_client, admin_test_user)
    headers = auth_headers(token)

    response = await api_client.post(
        "/api/v1/digests/news-impact",
        headers=headers,
        json={"processed_item_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROCESSED_ITEM_NOT_FOUND"
