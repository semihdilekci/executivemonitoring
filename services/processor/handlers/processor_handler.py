"""Lambda processor handler — SQS trigger → pipeline orchestrator (`Docs/04` §8.6–8.7)."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from services.processor.base_processor import ProcessorChain, ProcessorStepError
from services.processor.db_session import create_processor_redis, processor_db_session
from services.processor.models import (
    MessageParseError,
    ProcessedResult,
    ProcessorInput,
)
from services.processor.pipeline_orchestrator import (
    PipelineOrchestrator,
    build_translation_dependencies,
)

logger = logging.getLogger("ygip.processor.handler")


class RawItemLifecycle(Protocol):
    """raw_items.status geçişleri — test override veya DbRawItemLifecycle."""

    async def mark_processing(self, item: ProcessorInput) -> None: ...

    async def mark_processed(self, item: ProcessorInput, result: ProcessedResult) -> None: ...

    async def mark_failed(self, item: ProcessorInput, error: str) -> None: ...

    async def mark_skipped(self, item: ProcessorInput, result: ProcessedResult) -> None: ...


class NoOpRawItemLifecycle:
    """Unit test stub — DB status güncellemesi yok."""

    async def mark_processing(self, item: ProcessorInput) -> None:
        logger.debug(
            "raw_item_status_stub",
            extra={"status": "processing", "source_id": str(item.source_id)},
        )

    async def mark_processed(self, item: ProcessorInput, result: ProcessedResult) -> None:
        del result
        logger.debug(
            "raw_item_status_stub",
            extra={"status": "processed", "source_id": str(item.source_id)},
        )

    async def mark_failed(self, item: ProcessorInput, error: str) -> None:
        logger.debug(
            "raw_item_status_stub",
            extra={
                "status": "failed",
                "source_id": str(item.source_id),
                "error": error,
            },
        )

    async def mark_skipped(self, item: ProcessorInput, result: ProcessedResult) -> None:
        del result
        logger.debug(
            "raw_item_status_stub",
            extra={"status": "skipped", "source_id": str(item.source_id)},
        )


async def process_message(
    item: ProcessorInput,
    *,
    orchestrator: PipelineOrchestrator | None = None,
    chain: ProcessorChain | None = None,
    lifecycle: RawItemLifecycle | None = None,
) -> ProcessedResult:
    """Tek SQS mesajını pipeline'dan geçirir."""
    if orchestrator is not None:
        return await orchestrator.process(item)

    pipeline = chain if chain is not None else ProcessorChain()
    status_hook = lifecycle if lifecycle is not None else NoOpRawItemLifecycle()

    await status_hook.mark_processing(item)
    try:
        result = await pipeline.run(item)
    except ProcessorStepError as exc:
        error_message = str(exc.cause)
        await status_hook.mark_failed(item, error_message)
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

    if result.status == "success":
        await status_hook.mark_processed(item, result)
    elif result.status == "skipped":
        await status_hook.mark_skipped(item, result)
    return result


async def process_sqs_record(
    record: dict[str, Any],
    *,
    orchestrator: PipelineOrchestrator | None = None,
    chain: ProcessorChain | None = None,
    lifecycle: RawItemLifecycle | None = None,
) -> ProcessedResult:
    """SQS batch record → deserialize → pipeline."""
    message_id = str(record.get("messageId", ""))
    body = record.get("body")
    if not isinstance(body, str):
        raise MessageParseError("SQS record body string olmalı")

    item = ProcessorInput.from_sqs_body(body, sqs_message_id=message_id or None)

    if orchestrator is not None:
        return await orchestrator.process(item, sqs_body=body)

    return await process_message(item, chain=chain, lifecycle=lifecycle)


def _should_report_failure(result: ProcessedResult) -> bool:
    """Başarısız veya parse hatası → partial batch failure (DLQ redirect)."""
    return result.status == "failed"


async def handle_sqs_event(
    event: dict[str, Any],
    *,
    orchestrator: PipelineOrchestrator | None = None,
    chain: ProcessorChain | None = None,
    lifecycle: RawItemLifecycle | None = None,
) -> dict[str, list[dict[str, str]]]:
    """SQS Lambda event — partial batch failure response üretir."""
    batch_item_failures: list[dict[str, str]] = []
    records = event.get("Records", [])
    if not isinstance(records, list):
        logger.error("processor_invalid_event", extra={"reason": "Records missing"})
        return {"batchItemFailures": batch_item_failures}

    use_orchestrator = orchestrator is not None or (chain is None and lifecycle is None)

    for record in records:
        if not isinstance(record, dict):
            continue
        message_id = record.get("messageId")
        if not isinstance(message_id, str):
            continue

        try:
            if use_orchestrator and orchestrator is None:
                async with processor_db_session() as session:
                    redis = await create_processor_redis()
                    try:
                        translation_client, translation_min_score = (
                            await build_translation_dependencies(session)
                        )
                        orch = PipelineOrchestrator(
                            session=session,
                            redis=redis,
                            translation_llm_client=translation_client,
                            translation_min_score=translation_min_score,
                        )
                        result = await process_sqs_record(record, orchestrator=orch)
                    finally:
                        await redis.aclose()
            else:
                result = await process_sqs_record(
                    record,
                    orchestrator=orchestrator,
                    chain=chain,
                    lifecycle=lifecycle,
                )
            if _should_report_failure(result):
                batch_item_failures.append({"itemIdentifier": message_id})
        except MessageParseError:
            logger.exception(
                "processor_message_parse_failed",
                extra={"message_id": message_id},
            )
            batch_item_failures.append({"itemIdentifier": message_id})
        except Exception:
            logger.exception(
                "processor_unexpected_error",
                extra={"message_id": message_id},
            )
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, list[dict[str, str]]]:
    """AWS Lambda SQS trigger giriş noktası."""
    import asyncio

    chain_override = event.get("_processor_chain")
    lifecycle_override = event.get("_raw_item_lifecycle")
    orchestrator_override = event.get("_pipeline_orchestrator")
    chain = chain_override if isinstance(chain_override, ProcessorChain) else None
    lifecycle = lifecycle_override if lifecycle_override is not None else None
    orchestrator = (
        orchestrator_override if isinstance(orchestrator_override, PipelineOrchestrator) else None
    )

    sqs_event = event.get("_sqs_event", event)
    if not isinstance(sqs_event, dict):
        sqs_event = event

    return asyncio.run(
        handle_sqs_event(
            sqs_event,
            orchestrator=orchestrator,
            chain=chain,
            lifecycle=lifecycle,
        )
    )
