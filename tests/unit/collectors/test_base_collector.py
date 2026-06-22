"""BaseCollector framework unit testleri."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from packages.shared.enums import SourceCategory, SourceStatus, SourceType
from packages.shared.models.source import Source
from redis.asyncio import Redis
from services.collectors.base_collector import BaseCollector
from services.collectors.error_handler import (
    RETRY_DELAYS_SECONDS,
    DbCollectionAuditLogger,
    StubCollectionAuditLogger,
    StubCollectionNotifier,
    handle_collection_error,
    with_retry,
)
from services.collectors.handler import (
    register_collector,
    run_collector_batch,
    run_collector_for_source,
)
from services.collectors.models import RawArticle
from services.collectors.source_lifecycle import InMemorySourceFetchLifecycle
from services.collectors.sqs_publisher import SQSPublisher


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


class StubCollector(BaseCollector):
    source_type = SourceType.RSS

    def __init__(
        self,
        articles: list[RawArticle] | None = None,
        *,
        redis_client: Redis | None = None,
        collect_error: Exception | None = None,
    ) -> None:
        super().__init__(redis_client)
        self._articles = articles or []
        self._collect_error = collect_error
        self.collect_calls = 0

    async def collect(self, source: Source) -> list[RawArticle]:
        self.collect_calls += 1
        if self._collect_error is not None:
            raise self._collect_error
        return self._articles


@pytest.fixture(autouse=True)
def clear_collector_map() -> None:
    from services.collectors.handler import COLLECTOR_MAP, _register_default_collectors

    COLLECTOR_MAP.clear()
    yield
    COLLECTOR_MAP.clear()
    _register_default_collectors()


@pytest.fixture
def sample_article() -> RawArticle:
    source_id = uuid.uuid4()
    return RawArticle(
        source_id=source_id,
        title="  TCMB faiz kararı  ",
        content="  Temizlenecek içerik.  ",
        url="https://example.com/article/1",
        published_at=datetime(2026, 6, 16, 9, 0, tzinfo=UTC),
        metadata={"lang": "tr"},
        external_id="entry-1",
    )


@pytest.mark.asyncio
async def test_validate_rejects_empty_title(sample_article: RawArticle) -> None:
    collector = StubCollector()
    sample_article.title = "   "
    assert await collector.validate(sample_article) is False


@pytest.mark.asyncio
async def test_transform_produces_sha256_hash(sample_article: RawArticle) -> None:
    collector = StubCollector()
    normalized = await collector.transform(sample_article)

    assert normalized.title == "TCMB faiz kararı"
    assert normalized.content == "Temizlenecek içerik."
    assert normalized.url == "https://example.com/article/1"
    assert normalized.content_hash.startswith("sha256:")
    assert normalized.source_type == "rss"
    assert normalized.raw_metadata == {"lang": "tr"}


@pytest.mark.asyncio
async def test_dedup_check_returns_true_when_hash_exists() -> None:
    redis_mock = AsyncMock(spec=Redis)
    redis_mock.sismember = AsyncMock(return_value=True)
    collector = StubCollector(redis_client=redis_mock)

    is_duplicate = await collector.dedup_check("sha256:abc")

    assert is_duplicate is True
    redis_mock.sismember.assert_awaited_once_with("dedup:hashes", "sha256:abc")


@pytest.mark.asyncio
async def test_process_articles_skips_invalid_and_duplicates(sample_article: RawArticle) -> None:
    invalid = RawArticle(
        source_id=sample_article.source_id,
        title="",
        content="body",
        url="https://example.com/x",
    )
    redis_mock = AsyncMock(spec=Redis)
    redis_mock.sismember = AsyncMock(return_value=True)
    collector = StubCollector([sample_article, invalid], redis_client=redis_mock)
    publisher = AsyncMock()

    published = await collector.process_articles(
        _make_source(),
        [sample_article, invalid],
        publisher,
    )

    assert published == 0
    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_articles_publishes_valid_non_duplicate(sample_article: RawArticle) -> None:
    collector = StubCollector([sample_article])
    publisher = AsyncMock()

    published = await collector.process_articles(_make_source(), [sample_article], publisher)

    assert published == 1
    publisher.publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_with_retry_succeeds_on_first_attempt() -> None:
    operation = AsyncMock(return_value="ok")

    result = await with_retry(operation, delays=(0, 0, 0), max_retries=3)

    assert result == "ok"
    operation.assert_awaited_once()


@pytest.mark.asyncio
async def test_with_retry_uses_exponential_backoff() -> None:
    operation = AsyncMock(side_effect=[RuntimeError("fail"), RuntimeError("fail"), "ok"])

    with patch(
        "services.collectors.error_handler.asyncio.sleep",
        new_callable=AsyncMock,
    ) as sleep_mock:
        result = await with_retry(operation, delays=RETRY_DELAYS_SECONDS, max_retries=3)

    assert result == "ok"
    assert operation.await_count == 3
    sleep_mock.assert_any_await(2)
    sleep_mock.assert_any_await(4)


@pytest.mark.asyncio
async def test_with_retry_raises_after_max_retries() -> None:
    operation = AsyncMock(side_effect=RuntimeError("persistent"))

    with (
        patch(
            "services.collectors.error_handler.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        pytest.raises(RuntimeError, match="persistent"),
    ):
        await with_retry(operation, delays=(0, 0, 0), max_retries=2)

    assert operation.await_count == 3


@pytest.mark.asyncio
async def test_sqs_publisher_sends_json_message(sample_article: RawArticle) -> None:
    sqs_client = MagicMock()
    sqs_client.send_message.return_value = {"MessageId": "msg-123"}
    settings = MagicMock()
    settings.AWS_REGION = "eu-west-1"
    settings.queue_url_for_source_type.return_value = "https://sqs.eu-west-1.amazonaws.com/123/rss"

    publisher = SQSPublisher(settings=settings, sqs_client=sqs_client)
    collector = StubCollector()
    article = await collector.transform(sample_article)

    message_id = await publisher.publish(article)

    assert message_id == "msg-123"
    sqs_client.send_message.assert_called_once()
    call_kwargs = sqs_client.send_message.call_args.kwargs
    body = json.loads(call_kwargs["MessageBody"])
    assert body["source_id"] == str(sample_article.source_id)
    assert body["source_type"] == "rss"
    assert body["content_hash"].startswith("sha256:")
    assert call_kwargs["QueueUrl"] == "https://sqs.eu-west-1.amazonaws.com/123/rss"


@pytest.mark.asyncio
async def test_handle_collection_error_invokes_audit_and_notifier() -> None:
    source = _make_source()
    audit = AsyncMock(spec=StubCollectionAuditLogger)
    notifier = AsyncMock(spec=StubCollectionNotifier)

    await handle_collection_error(
        source=source,
        error=RuntimeError("connection timeout"),
        audit_logger=audit,
        notifier=notifier,
    )

    audit.log_collection_error.assert_awaited_once()
    notifier.notify_admin_collection_error.assert_awaited_once()


@pytest.mark.asyncio
async def test_db_collection_audit_logger_writes_system_error() -> None:
    source = _make_source()
    mock_session = MagicMock()
    mock_session.flush = AsyncMock()

    class _SessionContext:
        async def __aenter__(self) -> AsyncMock:
            return mock_session

        async def __aexit__(self, *args: object) -> bool:
            return False

    with patch(
        "services.collectors.error_handler.collector_db_session",
        return_value=_SessionContext(),
    ):
        audit_logger = DbCollectionAuditLogger()
        await audit_logger.log_collection_error(
            source=source,
            error_message="connection timeout",
            retry_count=3,
        )

    mock_session.add.assert_called_once()
    audit_log = mock_session.add.call_args.args[0]
    assert audit_log.event_type == "system.error"
    assert audit_log.target_type == "source"
    assert audit_log.target_id == source.id
    assert audit_log.payload["source_name"] == source.name
    assert audit_log.payload["error_message"] == "connection timeout"
    assert "password" not in audit_log.payload


@pytest.mark.asyncio
async def test_run_collector_for_source_skips_inactive_source() -> None:
    source = _make_source(status=SourceStatus.INACTIVE)
    collector = StubCollector()
    publisher = AsyncMock()

    count = await run_collector_for_source(collector, source, publisher)

    assert count == 0
    assert collector.collect_calls == 0


@pytest.mark.asyncio
async def test_run_collector_batch_uses_registered_collector(sample_article: RawArticle) -> None:
    source = _make_source()
    collector = StubCollector([sample_article])
    register_collector(SourceType.RSS, collector)
    publisher = AsyncMock()
    lifecycle = InMemorySourceFetchLifecycle({source.id: source})

    results = await run_collector_batch(
        "rss",
        [source],
        publisher,
        lifecycle=lifecycle,
    )

    assert results["published"] == 1
    assert results["sources_processed"] == 1
    assert results["sources_failed"] == 0
    assert source.error_count == 0
    assert source.last_fetched_at is not None
