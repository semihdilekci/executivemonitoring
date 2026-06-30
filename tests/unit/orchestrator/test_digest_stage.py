"""DigestStageExecutor + digest_update akış unit testleri (Faz 6.1 — İterasyon 5).

DB'siz / LLM'siz: digest runner mock'lanır (`Docs/04` §9 gerçek üretim çağrılmaz).
`digests.status` → step/run eşlemesi (`Docs/01` §5.3) ve `digest_update` run'ında
yalnızca digest aşamasının koştuğu (`Docs/01` §5.5) doğrulanır.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any

import pytest
from packages.shared.enums import (
    DigestStatus,
    PipelineRunStatus,
    PipelineRunType,
    PipelineStage,
    PipelineStepStatus,
)
from packages.shared.models.pipeline_run import PipelineRun
from packages.shared.models.pipeline_run_step import PipelineRunStep
from services.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from services.orchestrator.run_repository import DIGEST_UPDATE_SKIPPED, STAGE_SEQUENCE
from services.orchestrator.stage_executors import (
    DigestRequest,
    DigestRunResult,
    DigestStageExecutor,
    StageExecutor,
    StepResult,
)

pytestmark = pytest.mark.asyncio

_NEWSLETTER_TEMPLATE_ID = uuid.UUID("aa0e8400-0000-4000-8000-000000000001")


# --- Test doubles -----------------------------------------------------------


class _FakeDigestRunner:
    """Sabit `DigestRunResult` döndürür; aldığı `DigestRequest`'i saklar."""

    def __init__(self, result: DigestRunResult) -> None:
        self._result = result
        self.requests: list[DigestRequest] = []

    async def run(self, request: DigestRequest) -> DigestRunResult:
        self.requests.append(request)
        return self._result


def _digest_params(*, send_notification: bool = False) -> dict[str, Any]:
    return {
        "newsletter_template_id": str(_NEWSLETTER_TEMPLATE_ID),
        "period_start": "2026-06-09",
        "period_end": "2026-06-15",
        "send_notification": send_notification,
    }


def _build_step() -> PipelineRunStep:
    return PipelineRunStep(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        stage=PipelineStage.DIGEST,
        sequence=4,
        status=PipelineStepStatus.PENDING,
        detail={},
    )


def _build_run(
    *,
    params: dict[str, Any] | None = None,
    triggered_by: uuid.UUID | None = None,
) -> PipelineRun:
    return PipelineRun(
        id=uuid.uuid4(),
        run_type=PipelineRunType.DIGEST_UPDATE,
        status=PipelineRunStatus.RUNNING,
        source_types=[],
        params=params if params is not None else _digest_params(),
        stats={},
        triggered_by=triggered_by,
    )


# --- DigestStageExecutor birim davranışı ------------------------------------


async def test_digest_ready_marks_step_completed_and_records_id() -> None:
    digest_id = uuid.uuid4()
    runner = _FakeDigestRunner(
        DigestRunResult(status=DigestStatus.READY, digest_id=digest_id, section_count=3)
    )
    run = _build_run(triggered_by=uuid.uuid4())
    executor = DigestStageExecutor(runner=runner)

    result = await executor.run(run, _build_step())

    assert result.status == PipelineStepStatus.COMPLETED
    assert result.items_out == 3
    assert result.detail["digest_id"] == str(digest_id)
    assert result.detail["section_count"] == 3
    # digest_id run.stats'a yazıldı (canlı izleme + digest detay linki)
    assert run.stats["digest_id"] == str(digest_id)
    # Params runner'a doğru parse edildi
    request = runner.requests[0]
    assert request.newsletter_template_id == _NEWSLETTER_TEMPLATE_ID
    assert request.period_start == date(2026, 6, 9)
    assert request.actor_user_id == run.triggered_by
    assert request.send_notification is False


async def test_digest_failed_marks_step_failed_and_aborts() -> None:
    runner = _FakeDigestRunner(
        DigestRunResult(status=DigestStatus.FAILED, error="LLM key tükendi")
    )
    run = _build_run()
    executor = DigestStageExecutor(runner=runner)

    result = await executor.run(run, _build_step())

    assert result.status == PipelineStepStatus.FAILED
    assert result.abort is True
    assert result.error == "LLM key tükendi"
    assert "digest_id" not in run.stats


async def test_digest_detail_includes_diagnostics_and_captured_logs() -> None:
    digest_id = uuid.uuid4()
    diagnostics = {
        "candidate_count": 42,
        "dropped_count": 5,
        "defined_section_count": 5,
        "section_count": 4,
        "distribution": [
            {"sort_order": 0, "name": "A", "assigned_count": 3, "generated": True},
            {"sort_order": 4, "name": "E", "assigned_count": 0, "generated": False},
        ],
    }

    class _LoggingRunner:
        """Üretim sırasında ai_engine logu basar; diagnostikli sonuç döner."""

        async def run(self, request: DigestRequest) -> DigestRunResult:
            logging.getLogger("ygip.ai_engine.section_generator").warning(
                "section_no_articles_assigned",
                extra={"section": "E", "sort_order": 4},
            )
            return DigestRunResult(
                status=DigestStatus.READY,
                digest_id=digest_id,
                section_count=4,
                diagnostics=diagnostics,
            )

    executor = DigestStageExecutor(runner=_LoggingRunner())  # type: ignore[arg-type]

    result = await executor.run(_build_run(), _build_step())

    assert result.detail["diagnostics"] == diagnostics
    logs = result.detail["logs"]
    assert any(
        entry["message"] == "section_no_articles_assigned"
        and entry.get("context", {}).get("section") == "E"
        for entry in logs
    )


async def test_digest_send_notification_flag_passed_through() -> None:
    runner = _FakeDigestRunner(
        DigestRunResult(status=DigestStatus.READY, digest_id=uuid.uuid4())
    )
    run = _build_run(params=_digest_params(send_notification=True))
    executor = DigestStageExecutor(runner=runner)

    result = await executor.run(run, _build_step())

    assert runner.requests[0].send_notification is True
    assert result.detail["send_notification"] is True


async def test_invalid_digest_params_fail_without_calling_runner() -> None:
    runner = _FakeDigestRunner(
        DigestRunResult(status=DigestStatus.READY, digest_id=uuid.uuid4())
    )
    run = _build_run(params={"newsletter_template_id": "not-a-valid-uuid"})
    executor = DigestStageExecutor(runner=runner)

    result = await executor.run(run, _build_step())

    assert result.status == PipelineStepStatus.FAILED
    assert result.abort is True
    assert runner.requests == []


# --- digest_update orkestratör akışı ----------------------------------------


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSessionFactory:
    def __init__(self) -> None:
        self.session = _FakeSession()

    def __call__(self) -> _FakeSession:
        return self.session


class _FakeRunRepository:
    def __init__(self, run: PipelineRun) -> None:
        self._run = run

    async def get_run(self, _db: Any, run_id: uuid.UUID) -> PipelineRun | None:
        return self._run if self._run.id == run_id else None

    async def mark_run_running(self, _db: Any, run: PipelineRun) -> None:
        run.status = PipelineRunStatus.RUNNING

    async def start_step(self, _db: Any, step: PipelineRunStep) -> None:
        step.status = PipelineStepStatus.RUNNING

    async def advance_step(
        self,
        _db: Any,
        step: PipelineRunStep,
        *,
        status: PipelineStepStatus,
        items_in: int = 0,
        items_out: int = 0,
        items_failed: int = 0,
        detail: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        step.status = status
        step.items_in = items_in
        step.items_out = items_out
        step.items_failed = items_failed
        step.detail = detail or {}
        step.error_message = error

    async def skip_step(self, _db: Any, step: PipelineRunStep) -> None:
        step.status = PipelineStepStatus.SKIPPED

    async def finalize_run(
        self,
        _db: Any,
        run: PipelineRun,
        *,
        status: PipelineRunStatus,
        error_summary: str | None = None,
        stats: dict[str, Any] | None = None,
    ) -> None:
        run.status = status
        run.error_summary = error_summary
        if stats is not None:
            run.stats = stats


class _SpyExecutor:
    def __init__(self, stage: PipelineStage) -> None:
        self.stage = stage
        self.calls = 0

    async def run(self, run: PipelineRun, step: PipelineRunStep) -> StepResult:
        self.calls += 1
        return StepResult.completed(items_out=1)


def _build_digest_update_run() -> PipelineRun:
    run = PipelineRun(
        id=uuid.uuid4(),
        run_type=PipelineRunType.DIGEST_UPDATE,
        status=PipelineRunStatus.PENDING,
        source_types=[],
        params=_digest_params(),
        stats={},
        triggered_by=uuid.uuid4(),
    )
    steps: list[PipelineRunStep] = []
    for stage, sequence in STAGE_SEQUENCE.items():
        skipped = stage in DIGEST_UPDATE_SKIPPED
        steps.append(
            PipelineRunStep(
                id=uuid.uuid4(),
                run_id=run.id,
                stage=stage,
                sequence=sequence,
                status=(
                    PipelineStepStatus.SKIPPED if skipped else PipelineStepStatus.PENDING
                ),
                detail={},
            )
        )
    run.steps = steps
    return run


def _step(run: PipelineRun, stage: PipelineStage) -> PipelineRunStep:
    return next(s for s in run.steps if s.stage == stage)


async def test_digest_update_run_only_runs_digest_stage() -> None:
    run = _build_digest_update_run()
    digest_id = uuid.uuid4()
    digest_executor = DigestStageExecutor(
        runner=_FakeDigestRunner(
            DigestRunResult(
                status=DigestStatus.READY, digest_id=digest_id, section_count=2
            )
        )
    )
    spies = {
        stage: _SpyExecutor(stage)
        for stage in (PipelineStage.COLLECT, PipelineStage.INGEST, PipelineStage.PROCESS)
    }
    executors: dict[PipelineStage, StageExecutor] = {**spies, PipelineStage.DIGEST: digest_executor}
    orch = PipelineOrchestrator(
        session_factory=_FakeSessionFactory(),  # type: ignore[arg-type]
        executors=executors,
        repository=_FakeRunRepository(run),  # type: ignore[arg-type]
    )

    final = await orch.drive(run.id)

    assert final == PipelineRunStatus.COMPLETED
    assert _step(run, PipelineStage.DIGEST).status == PipelineStepStatus.COMPLETED
    assert run.stats["digest_id"] == str(digest_id)
    for stage in DIGEST_UPDATE_SKIPPED:
        assert _step(run, stage).status == PipelineStepStatus.SKIPPED
        assert spies[stage].calls == 0


async def test_digest_update_run_failed_when_digest_fails() -> None:
    run = _build_digest_update_run()
    digest_executor = DigestStageExecutor(
        runner=_FakeDigestRunner(
            DigestRunResult(status=DigestStatus.FAILED, error="kaynak veri yetersiz")
        )
    )
    executors: dict[PipelineStage, StageExecutor] = {PipelineStage.DIGEST: digest_executor}
    orch = PipelineOrchestrator(
        session_factory=_FakeSessionFactory(),  # type: ignore[arg-type]
        executors=executors,
        repository=_FakeRunRepository(run),  # type: ignore[arg-type]
    )

    final = await orch.drive(run.id)

    assert final == PipelineRunStatus.FAILED
    assert _step(run, PipelineStage.DIGEST).status == PipelineStepStatus.FAILED
    assert run.error_summary is not None and "kaynak veri yetersiz" in run.error_summary
