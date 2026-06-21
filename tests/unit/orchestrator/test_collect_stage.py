"""Collect + Ingest stage adapter unit testleri (Faz 6.1 — İterasyon 3).

Gerçek AWS yok: `CollectorInvoker` ve `RawItemCounter` mock'lanır (`Docs/08` §3.6).
Pozitif (2 tip invoke → sayaç), edge (bir tip hata → degraded/partial; tüm tipler
hata → abort), `["all"]` genişleme ve ingest gözlem stabilizasyonu doğrulanır.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from packages.shared.enums import (
    PipelineRunStatus,
    PipelineRunType,
    PipelineStage,
    PipelineStepStatus,
)
from packages.shared.models.pipeline_run import PipelineRun
from packages.shared.models.pipeline_run_step import PipelineRunStep
from services.orchestrator.aws_clients import InvokeResult, OrchestratorAwsSettings
from services.orchestrator.run_repository import STAGE_SEQUENCE
from services.orchestrator.stage_executors import (
    CollectStageExecutor,
    IngestStageExecutor,
)

pytestmark = pytest.mark.asyncio


# --- Test doubles -----------------------------------------------------------


class _FakeInvoker:
    """source_type → InvokeResult haritasıyla collector invoke'unu taklit eder."""

    def __init__(self, results: dict[str, InvokeResult]) -> None:
        self._results = results
        self.calls: list[str] = []

    async def invoke_collector(self, source_type: str) -> InvokeResult:
        self.calls.append(source_type)
        return self._results[source_type]


class _SequenceCounter:
    """Ardışık poll çağrılarında önceden tanımlı sayıları döner (son değer sabitlenir)."""

    def __init__(self, counts: list[int]) -> None:
        self._counts = counts
        self.calls = 0

    async def count_ingested(self, run: PipelineRun) -> int:
        index = min(self.calls, len(self._counts) - 1)
        self.calls += 1
        return self._counts[index]


def _ok(source_type: str, *, published: int, sources_failed: int = 0) -> InvokeResult:
    return InvokeResult(
        ok=True,
        source_type=source_type,
        status_code=200,
        request_id=f"req-{source_type}",
        payload={
            "published": published,
            "sources_processed": published,
            "sources_failed": sources_failed,
        },
    )


def _fail(source_type: str, error: str = "boom") -> InvokeResult:
    return InvokeResult(ok=False, source_type=source_type, error=error)


def _build_run(source_types: list[str]) -> PipelineRun:
    run = PipelineRun(
        id=uuid.uuid4(),
        run_type=PipelineRunType.COLLECT_PIPELINE,
        status=PipelineRunStatus.RUNNING,
        source_types=source_types,
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
    return run


def _step(run: PipelineRun, stage: PipelineStage) -> PipelineRunStep:
    return next(s for s in run.steps if s.stage == stage)


async def _noop_sleep(_seconds: float) -> None:
    return None


# --- Function name resolution -----------------------------------------------


async def test_collector_function_name_matches_infra_default() -> None:
    settings = OrchestratorAwsSettings()
    assert settings.collector_function_name("rss") == "dev-ygip-collector-rss"
    assert settings.collector_function_name("gov") == "dev-ygip-collector-gov"


async def test_collector_function_name_explicit_override() -> None:
    settings = OrchestratorAwsSettings(ORCH_COLLECTOR_FN_RSS="custom-rss-fn")
    assert settings.collector_function_name("rss") == "custom-rss-fn"


# --- LambdaInvoker response parsing (fake boto client) ----------------------


class _FakePayload:
    def __init__(self, raw: bytes) -> None:
        self._raw = raw

    def read(self) -> bytes:
        return self._raw


class _FakeLambdaClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.invoked_with: dict[str, Any] | None = None

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.invoked_with = kwargs
        return self._response


async def test_invoker_parses_successful_handler_body() -> None:
    import json as _json

    from services.orchestrator.aws_clients import LambdaInvoker

    body = {"published": 4, "sources_processed": 2, "sources_failed": 0}
    response = {
        "StatusCode": 200,
        "ResponseMetadata": {"RequestId": "abc-123"},
        "Payload": _FakePayload(_json.dumps({"statusCode": 200, "body": body}).encode()),
    }
    client = _FakeLambdaClient(response)
    invoker = LambdaInvoker(
        settings=OrchestratorAwsSettings(), lambda_client=client  # type: ignore[arg-type]
    )

    result = await invoker.invoke_collector("rss")

    assert result.ok is True
    assert result.payload["published"] == 4
    assert result.request_id == "abc-123"
    assert client.invoked_with is not None
    assert client.invoked_with["FunctionName"] == "dev-ygip-collector-rss"
    assert client.invoked_with["InvocationType"] == "RequestResponse"


async def test_invoker_flags_function_error() -> None:
    from services.orchestrator.aws_clients import LambdaInvoker

    response = {
        "StatusCode": 200,
        "FunctionError": "Unhandled",
        "ResponseMetadata": {"RequestId": "err-1"},
        "Payload": _FakePayload(b'{"errorMessage": "kaboom"}'),
    }
    invoker = LambdaInvoker(
        settings=OrchestratorAwsSettings(), lambda_client=_FakeLambdaClient(response)  # type: ignore[arg-type]
    )

    result = await invoker.invoke_collector("gov")

    assert result.ok is False
    assert result.error == "Unhandled"


# --- Collect stage ----------------------------------------------------------


async def test_collect_two_types_success_aggregates_published() -> None:
    run = _build_run(["rss", "gov"])
    invoker = _FakeInvoker({"rss": _ok("rss", published=3), "gov": _ok("gov", published=2)})
    executor = CollectStageExecutor(invoker=invoker)

    result = await executor.run(run, _step(run, PipelineStage.COLLECT))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.degraded is False
    assert result.items_out == 5
    assert result.items_failed == 0
    assert invoker.calls == ["rss", "gov"]
    assert result.detail["rss"]["ok"] is True
    assert result.detail["rss"]["request_id"] == "req-rss"


async def test_collect_one_type_fails_marks_degraded_partial() -> None:
    run = _build_run(["rss", "gov"])
    invoker = _FakeInvoker({"rss": _ok("rss", published=4), "gov": _fail("gov", "timeout")})
    executor = CollectStageExecutor(invoker=invoker)

    result = await executor.run(run, _step(run, PipelineStage.COLLECT))

    # Step completed kalır; degraded run seviyesinde partial'a yansır (`Docs/01` §5.5).
    assert result.status == PipelineStepStatus.COMPLETED
    assert result.degraded is True
    assert result.items_out == 4
    assert result.detail["gov"]["ok"] is False
    assert result.detail["gov"]["error"] == "timeout"


async def test_collect_source_level_failure_marks_degraded() -> None:
    run = _build_run(["rss"])
    invoker = _FakeInvoker({"rss": _ok("rss", published=2, sources_failed=1)})
    executor = CollectStageExecutor(invoker=invoker)

    result = await executor.run(run, _step(run, PipelineStage.COLLECT))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.degraded is True
    assert result.items_failed == 1


async def test_collect_all_types_fail_aborts_run() -> None:
    run = _build_run(["rss", "gov"])
    invoker = _FakeInvoker({"rss": _fail("rss"), "gov": _fail("gov")})
    executor = CollectStageExecutor(invoker=invoker)

    result = await executor.run(run, _step(run, PipelineStage.COLLECT))

    assert result.status == PipelineStepStatus.FAILED
    assert result.abort is True
    assert "başarısız" in (result.error or "")


async def test_collect_all_expands_active_types() -> None:
    run = _build_run(["all"])
    invoker = _FakeInvoker(
        {
            "rss": _ok("rss", published=1),
            "email": _ok("email", published=1),
            "gov": _ok("gov", published=1),
        }
    )

    async def _resolver() -> list[str]:
        # email + websocket aktif; websocket collector tipi değil → atlanır.
        return ["rss", "email", "websocket"]

    executor = CollectStageExecutor(invoker=invoker, active_types_resolver=_resolver)

    result = await executor.run(run, _step(run, PipelineStage.COLLECT))

    assert result.status == PipelineStepStatus.COMPLETED
    assert sorted(invoker.calls) == ["email", "rss"]
    assert result.items_out == 2


async def test_collect_unknown_type_filtered_then_aborts_when_empty() -> None:
    run = _build_run(["websocket"])  # collector tipi değil
    invoker = _FakeInvoker({})
    executor = CollectStageExecutor(invoker=invoker)

    result = await executor.run(run, _step(run, PipelineStage.COLLECT))

    assert result.status == PipelineStepStatus.FAILED
    assert result.abort is True
    assert invoker.calls == []


# --- Ingest stage -----------------------------------------------------------


async def test_ingest_reaches_expected_count() -> None:
    run = _build_run(["rss"])
    _step(run, PipelineStage.COLLECT).items_out = 3
    counter = _SequenceCounter([1, 2, 3, 3])
    executor = IngestStageExecutor(
        counter=counter, poll_interval=0.0, sleep=_noop_sleep
    )

    result = await executor.run(run, _step(run, PipelineStage.INGEST))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.items_out == 3
    assert result.items_in == 3
    assert result.items_failed == 0
    assert result.degraded is False


async def test_ingest_timeout_partial_when_below_expected() -> None:
    run = _build_run(["rss"])
    _step(run, PipelineStage.COLLECT).items_out = 5
    counter = _SequenceCounter([2, 2, 2, 2])  # stabilize at 2, expected 5
    executor = IngestStageExecutor(
        counter=counter, poll_interval=0.0, max_polls=6, stable_polls=2, sleep=_noop_sleep
    )

    result = await executor.run(run, _step(run, PipelineStage.INGEST))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.items_out == 2
    assert result.items_failed == 3
    assert result.degraded is True


async def test_ingest_zero_expected_completes_without_failure() -> None:
    run = _build_run(["rss"])
    _step(run, PipelineStage.COLLECT).items_out = 0
    counter = _SequenceCounter([0])
    executor = IngestStageExecutor(
        counter=counter, poll_interval=0.0, sleep=_noop_sleep
    )

    result = await executor.run(run, _step(run, PipelineStage.INGEST))

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.items_out == 0
    assert result.items_failed == 0
    assert result.degraded is False
