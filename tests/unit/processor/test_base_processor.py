"""Processor chain ve SQS handler unit testleri — iterasyon 3.1."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from services.processor.base_processor import (
    BaseProcessor,
    ProcessorChain,
    ProcessorStepError,
)
from services.processor.handlers.processor_handler import (
    NoOpRawItemLifecycle,
    handle_sqs_event,
    lambda_handler,
    process_message,
)
from services.processor.models import (
    MessageParseError,
    ProcessorContext,
    ProcessorInput,
    ProcessorOutput,
)


def _sample_input(**overrides: object) -> ProcessorInput:
    defaults: dict[str, object] = {
        "source_id": uuid.uuid4(),
        "source_type": "rss",
        "title": "TCMB faiz kararı açıklandı",
        "content": "Temizlenmiş makale içeriği processor test.",
        "content_hash": "sha256:processorunittesthash0000000000000000000000",
        "published_at": datetime.now(UTC),
        "raw_metadata": {"url": "https://example.com/1"},
        "url": "https://example.com/1",
        "external_id": "https://example.com/1",
        "collected_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return ProcessorInput(**defaults)  # type: ignore[arg-type]


def _sqs_body(**overrides: object) -> str:
    item = _sample_input(**overrides)
    payload: dict[str, Any] = {
        "source_id": str(item.source_id),
        "source_type": item.source_type,
        "title": item.title,
        "content": item.content,
        "content_hash": item.content_hash,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "collected_at": item.collected_at.isoformat() if item.collected_at else None,
        "raw_metadata": item.raw_metadata,
        "url": item.url,
        "external_id": item.external_id,
    }
    return json.dumps(payload, ensure_ascii=False)


class _AppendTagProcessor(BaseProcessor):
    def __init__(self, tag: str) -> None:
        self._tag = tag

    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        ctx.data.extras[self._tag] = True
        return ctx.data


class _DiscardProcessor(BaseProcessor):
    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        return None


class _FailingProcessor(BaseProcessor):
    async def process(self, ctx: ProcessorContext) -> ProcessorOutput | None:
        raise RuntimeError("boom")


def test_processor_input_rejects_numeric_source_id() -> None:
    with pytest.raises(MessageParseError, match="UUID string"):
        ProcessorInput.from_dict(
            {
                "source_id": 42,
                "source_type": "rss",
                "title": "t",
                "content": "c",
                "content_hash": "h",
            }
        )


def test_processor_input_from_sqs_body() -> None:
    source_id = uuid.uuid4()
    body = _sqs_body(source_id=source_id)
    item = ProcessorInput.from_sqs_body(body, sqs_message_id="msg-1")

    assert item.source_id == source_id
    assert item.source_type == "rss"
    assert item.sqs_message_id == "msg-1"


@pytest.mark.asyncio
async def test_chain_runs_processors_in_order() -> None:
    chain = ProcessorChain([_AppendTagProcessor("step1"), _AppendTagProcessor("step2")])
    result = await chain.run(_sample_input())

    assert result.status == "success"
    assert result.output is not None
    assert result.output.extras == {"step1": True, "step2": True}


@pytest.mark.asyncio
async def test_chain_stops_on_none_result() -> None:
    chain = ProcessorChain(
        [
            _AppendTagProcessor("before"),
            _DiscardProcessor(),
            _AppendTagProcessor("after"),
        ]
    )
    result = await chain.run(_sample_input())

    assert result.status == "skipped"
    assert result.processor_name == "_DiscardProcessor"
    assert result.skip_reason == "discarded_by__DiscardProcessor"


@pytest.mark.asyncio
async def test_chain_mid_step_exception_raises_processor_step_error() -> None:
    chain = ProcessorChain([_AppendTagProcessor("ok"), _FailingProcessor()])

    with pytest.raises(ProcessorStepError, match="_FailingProcessor"):
        await chain.run(_sample_input())


@pytest.mark.asyncio
async def test_process_message_maps_step_error_to_failed() -> None:
    chain = ProcessorChain([_FailingProcessor()])
    lifecycle = AsyncMock(spec=NoOpRawItemLifecycle)

    result = await process_message(_sample_input(), chain=chain, lifecycle=lifecycle)

    assert result.status == "failed"
    assert result.error == "boom"
    lifecycle.mark_processing.assert_awaited_once()
    lifecycle.mark_failed.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_skip_does_not_mark_processed() -> None:
    chain = ProcessorChain([_DiscardProcessor()])
    lifecycle = AsyncMock(spec=NoOpRawItemLifecycle)

    result = await process_message(_sample_input(), chain=chain, lifecycle=lifecycle)

    assert result.status == "skipped"
    lifecycle.mark_processing.assert_awaited_once()
    lifecycle.mark_processed.assert_not_awaited()
    lifecycle.mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_sqs_event_malformed_json_reports_batch_failure() -> None:
    event = {
        "Records": [
            {
                "messageId": "bad-json",
                "body": "not-json",
            }
        ]
    }

    response = await handle_sqs_event(event)

    assert response == {"batchItemFailures": [{"itemIdentifier": "bad-json"}]}


@pytest.mark.asyncio
async def test_handle_sqs_event_step_failure_reports_batch_failure() -> None:
    event = {
        "Records": [
            {
                "messageId": "fail-msg",
                "body": _sqs_body(),
            }
        ]
    }
    chain = ProcessorChain([_FailingProcessor()])

    response = await handle_sqs_event(event, chain=chain)

    assert response == {"batchItemFailures": [{"itemIdentifier": "fail-msg"}]}


@pytest.mark.asyncio
async def test_handle_sqs_event_success_empty_batch_failures() -> None:
    event = {
        "Records": [
            {
                "messageId": "ok-msg",
                "body": _sqs_body(),
            }
        ]
    }
    chain = ProcessorChain([_AppendTagProcessor("done")])

    response = await handle_sqs_event(event, chain=chain)

    assert response == {"batchItemFailures": []}


@pytest.mark.asyncio
async def test_handle_sqs_event_skip_is_not_batch_failure() -> None:
    event = {
        "Records": [
            {
                "messageId": "skip-msg",
                "body": _sqs_body(),
            }
        ]
    }
    chain = ProcessorChain([_DiscardProcessor()])

    response = await handle_sqs_event(event, chain=chain)

    assert response == {"batchItemFailures": []}


def test_lambda_handler_partial_batch_failure_format() -> None:
    chain = ProcessorChain([_FailingProcessor()])
    event = {
        "_sqs_event": {
            "Records": [
                {
                    "messageId": "lambda-fail",
                    "body": _sqs_body(),
                }
            ]
        },
        "_processor_chain": chain,
    }

    response = lambda_handler(event, None)

    assert response == {"batchItemFailures": [{"itemIdentifier": "lambda-fail"}]}
