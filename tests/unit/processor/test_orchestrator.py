"""PipelineOrchestrator unit testleri — persist fail rollback, happy path."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fakeredis.aioredis import FakeRedis
from services.processor.base_processor import ProcessorChain
from services.processor.embedding_service import DeterministicEmbeddingBackend, EmbeddingService
from services.processor.handlers.processor_handler import handle_sqs_event
from services.processor.models import ProcessedResult, ProcessorInput, ProcessorOutput
from services.processor.persistence import PersistResult
from services.processor.pipeline_orchestrator import PipelineOrchestrator

_FILLER = (
    "Piyasa analistleri bu hafta sonu gelişmeleri yakından izliyor "
    "ve yatırımcılar farklı senaryolar üzerinde değerlendirme yapıyor."
)


def _sample_input(**overrides: object) -> ProcessorInput:
    defaults: dict[str, object] = {
        "source_id": uuid.uuid4(),
        "source_type": "rss",
        "title": "TCMB faiz kararı",
        "content": _FILLER,
        "content_hash": "sha256:orchestratortesthash000000000000000000",
        "published_at": datetime.now(UTC),
        "raw_metadata": {},
    }
    defaults.update(overrides)
    return ProcessorInput(**defaults)  # type: ignore[arg-type]


def _success_output(item: ProcessorInput) -> ProcessorOutput:
    output = ProcessorOutput.from_input(item)
    output.extras = {
        "schema_category": "news",
        "clean_content": item.content,
        "language": "tr",
        "relevance_score": 0.8,
        "topics": ["faiz"],
        "entities": [],
        "chunks": [
            {
                "chunk_index": 0,
                "chunk_text": item.content,
                "token_count": 12,
            }
        ],
    }
    return output


class _SuccessChain(ProcessorChain):
    async def run(self, item: ProcessorInput) -> ProcessedResult:
        return ProcessedResult(status="success", output=_success_output(item))


@pytest.mark.asyncio
async def test_orchestrator_persist_failure_rolls_back_and_marks_failed() -> None:
    item = _sample_input()
    raw_item_id = uuid.uuid4()
    session = MagicMock()
    session.rollback = AsyncMock()
    lifecycle = MagicMock()
    lifecycle.mark_processing = AsyncMock()
    lifecycle.mark_failed = AsyncMock()
    lifecycle.mark_processed = AsyncMock()

    chain = _SuccessChain()
    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())
    orchestrator = PipelineOrchestrator(
        session=session,  # type: ignore[arg-type]
        redis=FakeRedis(),
        embedding_service=embedding,
        chain=chain,
    )
    orchestrator._lifecycle = lifecycle  # type: ignore[method-assign]

    with (
        patch(
            "services.processor.pipeline_orchestrator.resolve_raw_item_id",
            new_callable=AsyncMock,
            return_value=raw_item_id,
        ),
        patch(
            "services.processor.pipeline_orchestrator.persist_pipeline_output",
            new_callable=AsyncMock,
            side_effect=ValueError("chunk üretilmedi"),
        ),
    ):
        result = await orchestrator.process(item)

    assert result.status == "failed"
    assert result.error == "chunk üretilmedi"
    session.rollback.assert_awaited_once()
    lifecycle.mark_failed.assert_awaited_once_with(item, "chunk üretilmedi")
    lifecycle.mark_processed.assert_not_awaited()


@pytest.mark.asyncio
async def test_orchestrator_happy_path_persists_and_marks_processed() -> None:
    item = _sample_input()
    raw_item_id = uuid.uuid4()
    processed_id = uuid.uuid4()
    session = MagicMock()
    lifecycle = MagicMock()
    lifecycle.mark_processing = AsyncMock()
    lifecycle.mark_failed = AsyncMock()
    lifecycle.mark_processed = AsyncMock()

    chain = _SuccessChain()
    embedding = EmbeddingService(backend=DeterministicEmbeddingBackend())
    orchestrator = PipelineOrchestrator(
        session=session,  # type: ignore[arg-type]
        redis=FakeRedis(),
        embedding_service=embedding,
        chain=chain,
    )
    orchestrator._lifecycle = lifecycle  # type: ignore[method-assign]

    with (
        patch(
            "services.processor.pipeline_orchestrator.resolve_raw_item_id",
            new_callable=AsyncMock,
            return_value=raw_item_id,
        ),
        patch(
            "services.processor.pipeline_orchestrator.persist_pipeline_output",
            new_callable=AsyncMock,
            return_value=PersistResult(
                processed_item_id=processed_id,
                schema_category="news",
                chunk_count=1,
            ),
        ),
    ):
        result = await orchestrator.process(item)

    assert result.status == "success"
    lifecycle.mark_processed.assert_awaited_once()
    lifecycle.mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_sqs_event_orchestrator_persist_fail_reports_batch_failure() -> None:
    item = _sample_input()
    orchestrator = MagicMock()
    orchestrator.process = AsyncMock(
        return_value=ProcessedResult(status="failed", error="persist hatası"),
    )
    event = {
        "Records": [
            {
                "messageId": "msg-fail-1",
                "body": '{"source_id": "'
                + str(item.source_id)
                + '", "source_type": "rss", "title": "t", "content": "c", '
                '"content_hash": "h"}',
            }
        ]
    }

    response = await handle_sqs_event(event, orchestrator=orchestrator)

    assert response["batchItemFailures"] == [{"itemIdentifier": "msg-fail-1"}]
