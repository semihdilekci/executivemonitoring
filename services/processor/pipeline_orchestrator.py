"""Pipeline orchestrator — SQS mesajından DB persist'e uçtan uca akış."""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from services.collectors.persistence import IngestStatus, ingest_message
from services.processor.base_processor import ProcessorChain, ProcessorStepError, with_dedup_first
from services.processor.chunker import ChunkerProcessor
from services.processor.config import get_processor_settings
from services.processor.embedding_service import EmbeddingService, build_embedding_backend
from services.processor.enricher import EnricherProcessor
from services.processor.gate_processor import GateProcessor
from services.processor.keyword_pool import KeywordPoolProvider
from services.processor.keyword_repository import load_active_keywords
from services.processor.models import ProcessedResult, ProcessorInput
from services.processor.normalizer import NormalizerProcessor
from services.processor.persistence import persist_pipeline_output, resolve_raw_item_id
from services.processor.raw_item_lifecycle import DbRawItemLifecycle
from services.processor.scorer import ScorerProcessor
from services.processor.source_config_resolver import DbSourceConfigResolver

logger = logging.getLogger("ygip.processor.orchestrator")


def build_processor_chain(
    redis: Redis,
    *,
    source_config_resolver: DbSourceConfigResolver | None = None,
    keyword_pool_provider: KeywordPoolProvider | None = None,
) -> ProcessorChain:
    """Dedup → normalize → gate → enrich → score → chunk (`Docs/04` §8)."""
    resolver = source_config_resolver
    provider = keyword_pool_provider
    return with_dedup_first(
        redis,
        [
            NormalizerProcessor(),
            GateProcessor(resolver, keyword_pool_provider=provider),
            EnricherProcessor(resolver, keyword_pool_provider=provider),
            ScorerProcessor(),
            ChunkerProcessor(),
        ],
    )


class PipelineOrchestrator:
    """Tam processor zinciri + raw_item lifecycle + DB persist."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        redis: Redis,
        embedding_service: EmbeddingService | None = None,
        chain: ProcessorChain | None = None,
    ) -> None:
        self._session = session
        self._redis = redis
        self._lifecycle = DbRawItemLifecycle(session)
        settings = get_processor_settings()
        self._embedding = embedding_service or EmbeddingService(
            backend=build_embedding_backend(settings),
            batch_size=settings.EMBEDDING_BATCH_SIZE,
        )
        config_resolver = DbSourceConfigResolver(session)
        keyword_provider = KeywordPoolProvider(lambda: load_active_keywords(session))
        self._chain = chain or build_processor_chain(
            redis,
            source_config_resolver=config_resolver,
            keyword_pool_provider=keyword_provider,
        )

    @property
    def chain(self) -> ProcessorChain:
        return self._chain

    @property
    def lifecycle(self) -> DbRawItemLifecycle:
        return self._lifecycle

    async def process(
        self,
        item: ProcessorInput,
        *,
        sqs_body: str | None = None,
    ) -> ProcessedResult:
        """Tek SQS mesajını işler; başarıda processed_items + content_chunks yazar.

        `sqs_body` verilirse pipeline zincirinden **önce** idempotent `raw_item`
        ingest çalışır (`Docs/04` §8.0, ADR-0001). Duplicate → skip, invalid → DLQ
        path (failed). `sqs_body` None ise raw_item önceden seed edilmiş kabul edilir.
        """
        if sqs_body is not None:
            ingest = await ingest_message(self._session, sqs_body, redis=self._redis)
            if ingest.status is IngestStatus.DUPLICATE:
                logger.info(
                    "processor_ingest_duplicate",
                    extra={
                        "source_id": str(item.source_id),
                        "content_hash": item.content_hash,
                    },
                )
                return ProcessedResult(status="skipped", skip_reason="ingest_duplicate")
            if ingest.status is IngestStatus.INVALID:
                error_message = "ingest geçersiz mesaj"
                logger.warning(
                    "processor_ingest_invalid",
                    extra={"source_id": str(item.source_id)},
                )
                return ProcessedResult(status="failed", error=error_message)

        await self._lifecycle.mark_processing(item)
        try:
            result = await self._chain.run(item)
        except ProcessorStepError as exc:
            error_message = str(exc.cause)
            await self._lifecycle.mark_failed(item, error_message)
            logger.exception(
                "processor_pipeline_failed",
                extra={
                    "processor": exc.processor_name,
                    "source_id": str(item.source_id),
                    "content_hash": item.content_hash,
                },
            )
            return ProcessedResult(
                status="failed",
                error=error_message,
                processor_name=exc.processor_name,
            )

        if result.status == "skipped":
            await self._lifecycle.mark_skipped(item, result)
            return result

        if result.status != "success" or result.output is None:
            return result

        raw_item_id = await resolve_raw_item_id(self._session, item)
        if raw_item_id is None:
            error_message = "raw_item bulunamadı"
            await self._lifecycle.mark_failed(item, error_message)
            return ProcessedResult(status="failed", error=error_message)

        try:
            persist_result = await persist_pipeline_output(
                self._session,
                self._embedding,
                raw_item_id=raw_item_id,
                output=result.output,
            )
        except Exception as exc:
            error_message = str(exc)
            await self._session.rollback()
            await self._lifecycle.mark_failed(item, error_message)
            logger.exception(
                "processor_persist_failed",
                extra={
                    "source_id": str(item.source_id),
                    "raw_item_id": str(raw_item_id),
                },
            )
            return ProcessedResult(status="failed", error=error_message)

        if persist_result is None:
            logger.info(
                "processor_persist_idempotent",
                extra={
                    "source_id": str(item.source_id),
                    "raw_item_id": str(raw_item_id),
                },
            )

        await self._lifecycle.mark_processed(item, result)
        return result
