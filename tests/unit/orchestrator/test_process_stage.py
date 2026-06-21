"""Process stage adapter unit testleri (Faz 6.1 — İterasyon 4).

Gerçek AWS yok: `SqsObserver` mock'lanır (drain senaryoları) ve `BotoSqsObserver`
moto SQS ile gerçek queue derinliği üzerinden doğrulanır (`Docs/08` §3.6). Pozitif
(drain → completed, items_out doğru), edge (timeout → partial, processed delta=0,
DLQ → degraded) ve çok-tipli drain kapsanır (`Docs/04` §10.5).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import boto3
import pytest
from moto import mock_aws
from packages.shared.enums import (
    PipelineRunStatus,
    PipelineRunType,
    PipelineStage,
    PipelineStepStatus,
)
from packages.shared.models.pipeline_run import PipelineRun
from packages.shared.models.pipeline_run_step import PipelineRunStep
from services.orchestrator.aws_clients import (
    BotoSqsObserver,
    OrchestratorAwsSettings,
    QueueDepth,
)
from services.orchestrator.run_repository import STAGE_SEQUENCE
from services.orchestrator.stage_executors import ProcessStageExecutor

pytestmark = pytest.mark.asyncio


# --- Test doubles -----------------------------------------------------------


class _SequenceObserver:
    """source_type başına ardışık `QueueDepth` döndürür (son değer sabitlenir)."""

    def __init__(self, depths: dict[str, list[QueueDepth]]) -> None:
        self._depths = depths
        self.calls: dict[str, int] = {}

    async def queue_depth(self, source_type: str) -> QueueDepth:
        seq = self._depths[source_type]
        index = min(self.calls.get(source_type, 0), len(seq) - 1)
        self.calls[source_type] = self.calls.get(source_type, 0) + 1
        return seq[index]


class _SequenceCounter:
    """Ardışık poll çağrılarında önceden tanımlı processed sayıları döner."""

    def __init__(self, counts: list[int]) -> None:
        self._counts = counts
        self.calls = 0

    async def count_processed(self, run: PipelineRun) -> int:
        index = min(self.calls, len(self._counts) - 1)
        self.calls += 1
        return self._counts[index]


def _depth(visible: int = 0, not_visible: int = 0, dlq: int = 0) -> QueueDepth:
    return QueueDepth(
        source_type="rss", visible=visible, not_visible=not_visible, dlq=dlq
    )


def _build_run(
    *,
    collect_detail: dict[str, Any] | None = None,
    ingested: int = 0,
    source_types: list[str] | None = None,
) -> PipelineRun:
    run = PipelineRun(
        id=uuid.uuid4(),
        run_type=PipelineRunType.COLLECT_PIPELINE,
        status=PipelineRunStatus.RUNNING,
        source_types=source_types or ["rss"],
        params={},
        stats={},
        started_at=datetime.now(UTC),
    )
    run.steps = [
        PipelineRunStep(
            id=uuid.uuid4(),
            run_id=run.id,
            stage=stage,
            sequence=sequence,
            status=PipelineStepStatus.PENDING,
            items_in=0,
            items_out=0,
            items_failed=0,
            detail={},
        )
        for stage, sequence in STAGE_SEQUENCE.items()
    ]
    for step in run.steps:
        if step.stage == PipelineStage.COLLECT and collect_detail is not None:
            step.detail = collect_detail
        if step.stage == PipelineStage.INGEST:
            step.items_out = ingested
    return run


def _process_step(run: PipelineRun) -> PipelineRunStep:
    return next(s for s in run.steps if s.stage == PipelineStage.PROCESS)


async def _noop_sleep(_seconds: float) -> None:
    return None


def _executor(
    observer: _SequenceObserver, counter: _SequenceCounter, **kwargs: Any
) -> ProcessStageExecutor:
    return ProcessStageExecutor(
        observer=observer,
        counter=counter,
        poll_interval=0.0,
        sleep=_noop_sleep,
        **kwargs,
    )


# --- Drain happy path -------------------------------------------------------


async def test_process_drains_and_completes_with_correct_counts() -> None:
    run = _build_run(collect_detail={"rss": {"ok": True}}, ingested=3)
    observer = _SequenceObserver(
        {"rss": [_depth(visible=3), _depth(visible=1), _depth(), _depth()]}
    )
    counter = _SequenceCounter([1, 3, 3, 3])
    executor = _executor(observer, counter, max_polls=6, stable_polls=2)

    result = await executor.run(run, _process_step(run))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.degraded is False
    assert result.items_in == 3
    assert result.items_out == 3
    assert result.items_failed == 0
    assert result.detail["drained"] is True


async def test_process_observes_multiple_types_from_collect_detail() -> None:
    run = _build_run(
        collect_detail={"rss": {"ok": True}, "gov": {"ok": True}}, ingested=4
    )
    observer = _SequenceObserver(
        {
            "rss": [_depth(visible=1), _depth(), _depth()],
            "gov": [_depth(visible=2), _depth(), _depth()],
        }
    )
    counter = _SequenceCounter([4, 4, 4])
    executor = _executor(observer, counter, max_polls=6, stable_polls=2)

    result = await executor.run(run, _process_step(run))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.degraded is False
    assert set(result.detail["queues"]) == {"rss", "gov"}


# --- Edge cases -------------------------------------------------------------


async def test_process_timeout_marks_partial_when_queue_never_drains() -> None:
    run = _build_run(collect_detail={"rss": {"ok": True}}, ingested=5)
    observer = _SequenceObserver({"rss": [_depth(visible=2)]})  # hiç drain olmaz
    counter = _SequenceCounter([2])  # processed 2'de sabit
    executor = _executor(observer, counter, max_polls=4, stable_polls=2)

    result = await executor.run(run, _process_step(run))

    assert result.status == PipelineStepStatus.COMPLETED  # step completed, run partial
    assert result.degraded is True
    assert result.detail["drained"] is False
    assert result.detail["drain_polls"] == 4
    assert result.items_out == 2
    assert result.items_failed == 3


async def test_process_zero_processed_but_drained_is_degraded() -> None:
    run = _build_run(collect_detail={"rss": {"ok": True}}, ingested=4)
    observer = _SequenceObserver({"rss": [_depth()]})  # baştan boş
    counter = _SequenceCounter([0])  # hiçbir şey işlenmedi
    executor = _executor(observer, counter, max_polls=6, stable_polls=2)

    result = await executor.run(run, _process_step(run))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.degraded is True
    assert result.items_out == 0
    assert result.items_failed == 4


async def test_process_dlq_depth_marks_degraded() -> None:
    run = _build_run(collect_detail={"rss": {"ok": True}}, ingested=3)
    observer = _SequenceObserver({"rss": [_depth(dlq=1)]})  # drain ama 1 DLQ'da
    counter = _SequenceCounter([2])
    executor = _executor(observer, counter, max_polls=6, stable_polls=2)

    result = await executor.run(run, _process_step(run))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.degraded is True
    assert result.detail["dlq"] == 1
    assert result.items_failed == 1


async def test_process_no_collector_types_completes_immediately() -> None:
    # digest_update dışı ama collect detail boş + source_types collector tipi değil →
    # izlenecek queue yok; processed stabilize olunca tamamlanır.
    run = _build_run(ingested=0, source_types=["websocket"])
    observer = _SequenceObserver({})
    counter = _SequenceCounter([0])
    executor = _executor(observer, counter, max_polls=6, stable_polls=2)

    result = await executor.run(run, _process_step(run))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.degraded is False
    assert result.detail["queues"] == {}


# --- BotoSqsObserver (moto SQS) ---------------------------------------------


async def test_boto_observer_reads_queue_and_dlq_depth() -> None:
    with mock_aws():
        client = boto3.client(
            "sqs",
            region_name="eu-west-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        main = client.create_queue(QueueName="dev-ygip-sqs-rss")["QueueUrl"]
        dlq = client.create_queue(QueueName="dev-ygip-sqs-rss-dlq")["QueueUrl"]
        client.send_message(QueueUrl=main, MessageBody="a")
        client.send_message(QueueUrl=main, MessageBody="b")
        client.send_message(QueueUrl=dlq, MessageBody="dead")

        observer = BotoSqsObserver(
            settings=OrchestratorAwsSettings(),
            sqs_client=client,  # type: ignore[arg-type]
        )
        depth = await observer.queue_depth("rss")

    assert depth.source_type == "rss"
    assert depth.visible == 2
    assert depth.is_drained is False
    assert depth.dlq == 1


async def test_boto_observer_missing_queue_counts_zero() -> None:
    with mock_aws():
        client = boto3.client(
            "sqs",
            region_name="eu-west-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        # Hiç queue yaratılmadı → get_queue_url QueueDoesNotExist → derinlik 0.
        observer = BotoSqsObserver(
            settings=OrchestratorAwsSettings(),
            sqs_client=client,  # type: ignore[arg-type]
        )
        depth = await observer.queue_depth("rss")

    assert depth.visible == 0
    assert depth.dlq == 0
    assert depth.is_drained is True


async def test_boto_observer_uses_url_override_without_resolution() -> None:
    with mock_aws():
        client = boto3.client(
            "sqs",
            region_name="eu-west-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        main = client.create_queue(QueueName="custom-rss")["QueueUrl"]
        client.send_message(QueueUrl=main, MessageBody="a")

        settings = OrchestratorAwsSettings(ORCH_SQS_QUEUE_RSS_URL=main)
        observer = BotoSqsObserver(settings=settings, sqs_client=client)  # type: ignore[arg-type]
        depth = await observer.queue_depth("rss")

    assert depth.visible == 1
