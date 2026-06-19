"""Collector handler unit testleri — batch, lambda, hata yolları."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from services.collectors.handler import (
    COLLECTOR_MAP,
    lambda_handler,
    run_collector_batch,
)
from services.collectors.models import RawArticle
from services.collectors.source_lifecycle import InMemorySourceFetchLifecycle


def _make_source(**overrides: object) -> Source:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Test RSS",
        "source_type": SourceType.RSS,
        "config": {"feed_url": "https://example.com/feed.xml"},
        "polling_interval_minutes": 15,
        "status": SourceStatus.ACTIVE,
        "error_count": 0,
        "category": SourceCategory.TURKISH_MEDIA,
        "target_phase": "mvp-0",
    }
    defaults.update(overrides)
    return Source(**defaults)  # type: ignore[arg-type]


class _StubCollector:
    def __init__(
        self,
        articles: list[RawArticle] | None = None,
        *,
        collect_error: Exception | None = None,
    ) -> None:
        self._articles = articles or []
        self._collect_error = collect_error

    async def collect(self, source: Source) -> list[RawArticle]:
        if self._collect_error is not None:
            raise self._collect_error
        return self._articles

    async def process_articles(
        self,
        source: Source,
        articles: list[RawArticle],
        publisher: object,
    ) -> int:
        return len(articles)


@pytest.fixture(autouse=True)
def clear_collector_map() -> None:
    from services.collectors.handler import _register_default_collectors

    COLLECTOR_MAP.clear()
    yield
    COLLECTOR_MAP.clear()
    _register_default_collectors()


def test_lambda_handler_requires_source_type() -> None:
    result = lambda_handler({}, None)

    assert result["statusCode"] == 400
    assert result["body"] == "source_type required"


def test_lambda_handler_with_sources_loader() -> None:
    source = _make_source()
    article = RawArticle(
        source_id=source.id,
        title="Başlık",
        content="İçerik",
        url="https://example.com/1",
    )
    collector = _StubCollector([article])
    COLLECTOR_MAP["rss"] = collector  # type: ignore[assignment]

    async def _loader(source_type: str) -> list[Source]:
        assert source_type == "rss"
        return [source]

    with patch(
        "services.collectors.handler.run_collector_batch",
        new_callable=AsyncMock,
        return_value={"published": 1, "sources_processed": 1, "sources_failed": 0},
    ) as batch_mock:
        result = lambda_handler(
            {
                "source_type": "rss",
                "_sources_loader": _loader,
            },
            None,
        )

    assert result["statusCode"] == 200
    batch_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_collector_batch_raises_for_unknown_source_type() -> None:
    with pytest.raises(KeyError, match="Collector tanımlı değil"):
        await run_collector_batch("unknown", [])


@pytest.mark.asyncio
async def test_run_collector_batch_counts_failed_sources() -> None:
    source = _make_source()
    failing = _StubCollector(collect_error=RuntimeError("boom"))
    COLLECTOR_MAP["rss"] = failing  # type: ignore[assignment]
    publisher = AsyncMock()
    lifecycle = InMemorySourceFetchLifecycle({source.id: source})

    with patch("services.collectors.error_handler.asyncio.sleep", new_callable=AsyncMock):
        from services.collectors.error_handler import StubCollectionAuditLogger

        results = await run_collector_batch(
            "rss",
            [source],
            publisher,
            lifecycle=lifecycle,
            audit_logger=StubCollectionAuditLogger(),
        )

    assert results["sources_failed"] == 1
    assert results["sources_processed"] == 0
    assert source.error_count == 1
