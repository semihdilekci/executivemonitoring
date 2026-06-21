"""Lambda collector handler — EventBridge tetikleyici giriş noktası."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from packages.shared.enums import SourceStatus, SourceType
from packages.shared.models.source import Source
from redis.asyncio import Redis

from services.collectors.base_collector import BaseCollector
from services.collectors.email_collector import EmailCollector
from services.collectors.error_handler import (
    CollectionAuditLogger,
    CollectionNotifier,
    handle_collection_error,
    with_retry,
)
from services.collectors.gov_collector import GovCollector
from services.collectors.rss_collector import RSSCollector
from services.collectors.source_lifecycle import (
    SourceFetchLifecycle,
    default_fetch_lifecycle,
)
from services.collectors.sqs_publisher import SQSPublisher, SQSPublisherProtocol

logger = logging.getLogger("ygip.collectors.handler")

COLLECTOR_MAP: dict[str, BaseCollector] = {}


def register_collector(source_type: SourceType, collector: BaseCollector) -> None:
    """COLLECTOR_MAP'e collector kaydı — test ve ileriki iterasyonlar için."""
    COLLECTOR_MAP[source_type.value] = collector


def _register_default_collectors() -> None:
    register_collector(SourceType.RSS, RSSCollector())
    register_collector(SourceType.EMAIL, EmailCollector())
    register_collector(SourceType.GOV, GovCollector())


_register_default_collectors()


async def run_collector_for_source(
    collector: BaseCollector,
    source: Source,
    publisher: SQSPublisherProtocol,
    *,
    audit_logger: CollectionAuditLogger | None = None,
    notifier: CollectionNotifier | None = None,
    lifecycle: SourceFetchLifecycle | None = None,
) -> int:
    """Tek kaynak için collect → retry → publish pipeline."""
    if source.status != SourceStatus.ACTIVE:
        logger.info(
            "collector_source_skipped",
            extra={"source_id": str(source.id), "status": source.status.value},
        )
        return 0

    fetch_lifecycle = lifecycle if lifecycle is not None else default_fetch_lifecycle()

    try:
        articles = await with_retry(lambda: collector.collect(source))
        count = await collector.process_articles(source, articles, publisher)
        if count == 0:
            # Çekim teknik olarak başarılı ama hiç içerik yayınlanmadı — sessiz
            # "başarı/0 içerik" durumu yanlış konfigürasyonu (ör. bayatlamış RSS
            # URL'si, RSS bekleyip JSON dönen endpoint) maskeler. raw_count ayrımı:
            # 0 ise kaynak hiç içerik döndürmedi (feed/API sorunu); >0 ise tüm
            # makaleler validation/dedup'ta düştü.
            logger.warning(
                "collector_zero_content",
                extra={
                    "source_id": str(source.id),
                    "source_name": source.name,
                    "source_type": source.source_type.value,
                    "raw_count": len(articles),
                },
            )
        await fetch_lifecycle.record_success(source.id)
        return count
    except Exception as exc:
        await fetch_lifecycle.record_failure(source.id)
        await handle_collection_error(
            source=source,
            error=exc,
            audit_logger=audit_logger,
            notifier=notifier,
        )
        raise


async def run_collector_batch(
    source_type: str,
    sources: list[Source],
    publisher: SQSPublisherProtocol | None = None,
    *,
    audit_logger: CollectionAuditLogger | None = None,
    notifier: CollectionNotifier | None = None,
    lifecycle: SourceFetchLifecycle | None = None,
    redis_client: Redis | None = None,
) -> dict[str, int]:
    """Aktif kaynak listesi üzerinde collector çalıştırır."""
    collector = COLLECTOR_MAP.get(source_type)
    if collector is None:
        msg = f"Collector tanımlı değil: source_type={source_type}"
        raise KeyError(msg)

    # URL-cache (tekrar fetch önleme) için redis'i singleton collector'a bağla.
    if redis_client is not None:
        collector.bind_redis(redis_client)

    sqs = publisher or SQSPublisher()
    results: dict[str, int] = {
        "published": 0,
        "sources_processed": 0,
        "sources_failed": 0,
        "sources_empty": 0,
    }

    for source in sources:
        try:
            count = await run_collector_for_source(
                collector,
                source,
                sqs,
                audit_logger=audit_logger,
                notifier=notifier,
                lifecycle=lifecycle,
            )
            results["published"] += count
            results["sources_processed"] += 1
            # "İşlendi ama 0 içerik" sayısı — pipeline özetinde dejenere kaynakları
            # görünür kılar (başarılı görünüp içerik düşmeyen kaynaklar).
            if count == 0:
                results["sources_empty"] += 1
        except Exception:
            results["sources_failed"] += 1
            logger.exception(
                "collector_source_failed",
                extra={"source_id": str(source.id), "source_type": source_type},
            )

    return results


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda senkron giriş — async pipeline'ı çalıştırır."""
    import asyncio

    source_type = event.get("source_type")
    if not isinstance(source_type, str):
        return {"statusCode": 400, "body": "source_type required"}

    sources_loader: Callable[[str], Awaitable[list[Source]]] | None = event.get("_sources_loader")

    async def _run() -> dict[str, int]:
        if sources_loader is not None:
            sources = await sources_loader(source_type)
        else:
            from services.collectors.source_loader import load_active_sources

            sources = await load_active_sources(source_type)
        return await run_collector_batch(source_type, sources)

    results = asyncio.run(_run())
    return {"statusCode": 200, "body": results}
