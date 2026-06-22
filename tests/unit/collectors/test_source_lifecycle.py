"""Source fetch lifecycle unit testleri — F-02-001, F-02-004."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from services.collectors.error_handler import RETRY_DELAYS_SECONDS, StubCollectionAuditLogger
from services.collectors.handler import run_collector_for_source
from services.collectors.models import RawArticle
from services.collectors.source_lifecycle import (
    ERROR_COUNT_THRESHOLD,
    InMemorySourceFetchLifecycle,
    apply_fetch_failure,
    apply_fetch_success,
)


def _make_source(**overrides: object) -> Source:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Test RSS",
        "source_type": SourceType.RSS,
        "config": {"feed_url": "https://example.com/feed.xml"},
        "polling_interval_minutes": 15,
        "status": SourceStatus.ACTIVE,
        "error_count": 0,
        "category": SourceCategory.MACRO,
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
        self.collect_calls = 0

    async def collect(self, source: Source) -> list[RawArticle]:
        self.collect_calls += 1
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


def test_apply_fetch_success_resets_error_count_and_sets_timestamp() -> None:
    source = _make_source(error_count=2)

    apply_fetch_success(source)

    assert source.error_count == 0
    assert source.last_fetched_at is not None


def test_apply_fetch_failure_increments_error_count() -> None:
    source = _make_source(error_count=0)

    apply_fetch_failure(source)

    assert source.error_count == 1
    assert source.status == SourceStatus.ACTIVE


def test_apply_fetch_failure_sets_error_status_at_threshold() -> None:
    source = _make_source(error_count=ERROR_COUNT_THRESHOLD - 1)

    apply_fetch_failure(source)

    assert source.error_count == ERROR_COUNT_THRESHOLD
    assert source.status == SourceStatus.ERROR


@pytest.mark.asyncio
async def test_in_memory_lifecycle_record_success() -> None:
    source = _make_source(error_count=1)
    lifecycle = InMemorySourceFetchLifecycle({source.id: source})

    await lifecycle.record_success(source.id)

    assert source.error_count == 0
    assert source.last_fetched_at is not None


@pytest.mark.asyncio
async def test_in_memory_lifecycle_record_failure() -> None:
    source = _make_source(error_count=2)
    lifecycle = InMemorySourceFetchLifecycle({source.id: source})

    await lifecycle.record_failure(source.id)

    assert source.error_count == 3
    assert source.status == SourceStatus.ERROR


@pytest.mark.asyncio
async def test_run_collector_success_updates_lifecycle() -> None:
    source = _make_source(error_count=2)
    lifecycle = InMemorySourceFetchLifecycle({source.id: source})
    article = RawArticle(
        source_id=source.id,
        title="Başlık",
        content="İçerik",
        url="https://example.com/1",
    )
    collector = _StubCollector([article])
    publisher = AsyncMock()

    count = await run_collector_for_source(
        collector,  # type: ignore[arg-type]
        source,
        publisher,
        lifecycle=lifecycle,
    )

    assert count == 1
    assert source.error_count == 0
    assert source.last_fetched_at is not None


@pytest.mark.asyncio
async def test_run_collector_failure_increments_error_count() -> None:
    source = _make_source(error_count=0)
    lifecycle = InMemorySourceFetchLifecycle({source.id: source})
    collector = _StubCollector(collect_error=RuntimeError("persistent"))
    publisher = AsyncMock()
    audit = StubCollectionAuditLogger()

    with (
        patch(
            "services.collectors.error_handler.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        pytest.raises(RuntimeError, match="persistent"),
    ):
        await run_collector_for_source(
            collector,  # type: ignore[arg-type]
            source,
            publisher,
            lifecycle=lifecycle,
            audit_logger=audit,
        )

    assert source.error_count == 1
    assert source.status == SourceStatus.ACTIVE


@pytest.mark.asyncio
async def test_run_collector_third_failure_sets_error_status() -> None:
    source = _make_source(error_count=2)
    lifecycle = InMemorySourceFetchLifecycle({source.id: source})
    collector = _StubCollector(collect_error=RuntimeError("persistent"))
    publisher = AsyncMock()
    audit = StubCollectionAuditLogger()

    with (
        patch(
            "services.collectors.error_handler.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        pytest.raises(RuntimeError, match="persistent"),
    ):
        await run_collector_for_source(
            collector,  # type: ignore[arg-type]
            source,
            publisher,
            lifecycle=lifecycle,
            audit_logger=audit,
        )

    assert source.error_count == 3
    assert source.status == SourceStatus.ERROR


@pytest.mark.asyncio
async def test_inactive_source_skip_does_not_update_lifecycle() -> None:
    source = _make_source(status=SourceStatus.INACTIVE, error_count=2)
    lifecycle = InMemorySourceFetchLifecycle({source.id: source})
    collector = _StubCollector()
    publisher = AsyncMock()

    count = await run_collector_for_source(
        collector,  # type: ignore[arg-type]
        source,
        publisher,
        lifecycle=lifecycle,
    )

    assert count == 0
    assert collector.collect_calls == 0
    assert source.error_count == 2
    assert source.last_fetched_at is None


@pytest.mark.asyncio
async def test_db_source_fetch_lifecycle_record_success() -> None:
    source = _make_source(error_count=2)
    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = source
    mock_session.execute = AsyncMock(return_value=mock_result)

    class _SessionContext:
        async def __aenter__(self) -> AsyncMock:
            return mock_session

        async def __aexit__(self, *args: object) -> bool:
            return False

    from services.collectors.source_lifecycle import DbSourceFetchLifecycle

    with patch(
        "services.collectors.source_lifecycle.collector_db_session",
        return_value=_SessionContext(),
    ):
        lifecycle = DbSourceFetchLifecycle()
        await lifecycle.record_success(source.id)

    assert source.error_count == 0
    assert source.last_fetched_at is not None
    mock_session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_with_retry_delays_before_failure_lifecycle() -> None:
    """3 retry tamamlandıktan sonra tek error_count artışı (`Docs/01`)."""
    source = _make_source(error_count=0)
    lifecycle = InMemorySourceFetchLifecycle({source.id: source})
    collector = _StubCollector(collect_error=RuntimeError("fail"))
    publisher = AsyncMock()
    audit = StubCollectionAuditLogger()

    with (
        patch(
            "services.collectors.error_handler.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep_mock,
        pytest.raises(RuntimeError, match="fail"),
    ):
        await run_collector_for_source(
            collector,  # type: ignore[arg-type]
            source,
            publisher,
            lifecycle=lifecycle,
            audit_logger=audit,
        )

    assert collector.collect_calls == 4  # 1 initial + 3 retries
    assert sleep_mock.await_count == 3
    assert sleep_mock.await_args_list[0].args == (RETRY_DELAYS_SECONDS[0],)
    assert source.error_count == 1
