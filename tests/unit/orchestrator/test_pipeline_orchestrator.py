"""PipelineOrchestrator state machine unit testleri (Faz 6.1 — İterasyon 2).

DB'siz: in-memory ORM instance + fake repository/session. Gerçek invoke yok —
stub/sayan executor'larla state machine geçişleri doğrulanır (`Docs/01` §5.5).
"""

from __future__ import annotations

import uuid
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
from services.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from services.orchestrator.run_repository import (
    DIGEST_UPDATE_SKIPPED,
    STAGE_SEQUENCE,
    _skipped_stages,
)
from services.orchestrator.stage_executors import StageExecutor, StepResult

pytestmark = pytest.mark.asyncio


# --- Test doubles -----------------------------------------------------------


class _FakeSession:
    """No-op async session — commit'leri sayar, başka iş yapmaz."""

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
    """In-memory run/step deposu — orkestratör mutasyonlarını uygular."""

    def __init__(self, run: PipelineRun | None) -> None:
        self._run = run

    async def get_run(self, _db: Any, run_id: uuid.UUID) -> PipelineRun | None:
        if self._run is not None and self._run.id == run_id:
            return self._run
        return None

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


class _CountingExecutor:
    """Verilen `StepResult`'ı döndürür ve çağrı sayısını izler."""

    def __init__(self, stage: PipelineStage, result: StepResult) -> None:
        self.stage = stage
        self._result = result
        self.calls = 0

    async def run(self, run: PipelineRun, step: PipelineRunStep) -> StepResult:
        self.calls += 1
        return self._result


class _RaisingExecutor:
    def __init__(self, stage: PipelineStage) -> None:
        self.stage = stage
        self.calls = 0

    async def run(self, run: PipelineRun, step: PipelineRunStep) -> StepResult:
        self.calls += 1
        raise RuntimeError("boom")


# --- Fixtures / helpers -----------------------------------------------------


def _build_run(run_type: PipelineRunType) -> PipelineRun:
    run = PipelineRun(
        id=uuid.uuid4(),
        run_type=run_type,
        status=PipelineRunStatus.PENDING,
        source_types=["rss"],
        params={},
        stats={},
    )
    skipped_stages = _skipped_stages(run_type)
    steps: list[PipelineRunStep] = []
    for stage, sequence in STAGE_SEQUENCE.items():
        skipped = stage in skipped_stages
        steps.append(
            PipelineRunStep(
                id=uuid.uuid4(),
                run_id=run.id,
                stage=stage,
                sequence=sequence,
                status=(
                    PipelineStepStatus.SKIPPED if skipped else PipelineStepStatus.PENDING
                ),
                items_in=0,
                items_out=0,
                items_failed=0,
                detail={},
            )
        )
    run.steps = steps
    return run


def _orchestrator(
    run: PipelineRun, executors: dict[PipelineStage, StageExecutor]
) -> tuple[PipelineOrchestrator, _FakeRunRepository]:
    repo = _FakeRunRepository(run)
    orch = PipelineOrchestrator(
        session_factory=_FakeSessionFactory(),  # type: ignore[arg-type]
        executors=executors,
        repository=repo,  # type: ignore[arg-type]
    )
    return orch, repo


def _all_completed_executors() -> dict[PipelineStage, _CountingExecutor]:
    return {
        stage: _CountingExecutor(stage, StepResult.completed(items_out=5))
        for stage in PipelineStage
    }


def _step(run: PipelineRun, stage: PipelineStage) -> PipelineRunStep:
    return next(s for s in run.steps if s.stage == stage)


# --- Tests ------------------------------------------------------------------


async def test_collect_pipeline_runs_collect_ingest_process_skips_digest() -> None:
    run = _build_run(PipelineRunType.COLLECT_PIPELINE)
    executors = _all_completed_executors()
    orch, _ = _orchestrator(run, executors)

    final = await orch.drive(run.id)

    assert final == PipelineRunStatus.COMPLETED
    assert run.status == PipelineRunStatus.COMPLETED
    # collect_pipeline'da digest baştan skipped; collect/ingest/process koşar.
    for stage in (PipelineStage.COLLECT, PipelineStage.INGEST, PipelineStage.PROCESS):
        assert _step(run, stage).status == PipelineStepStatus.COMPLETED
        assert executors[stage].calls == 1
    assert _step(run, PipelineStage.DIGEST).status == PipelineStepStatus.SKIPPED
    assert executors[PipelineStage.DIGEST].calls == 0
    assert run.error_summary is None


async def test_executor_failure_marks_run_partial() -> None:
    run = _build_run(PipelineRunType.COLLECT_PIPELINE)
    executors = _all_completed_executors()
    executors[PipelineStage.INGEST] = _CountingExecutor(
        PipelineStage.INGEST, StepResult.failed("ingest patladı")
    )
    orch, _ = _orchestrator(run, dict(executors))

    final = await orch.drive(run.id)

    assert final == PipelineRunStatus.PARTIAL
    assert run.status == PipelineRunStatus.PARTIAL
    assert _step(run, PipelineStage.INGEST).status == PipelineStepStatus.FAILED
    # Sonraki aşamalar yine de koşar (abort yok); digest collect_pipeline'da skipped.
    assert _step(run, PipelineStage.PROCESS).status == PipelineStepStatus.COMPLETED
    assert _step(run, PipelineStage.DIGEST).status == PipelineStepStatus.SKIPPED
    assert run.error_summary is not None and "ingest patladı" in run.error_summary


async def test_executor_exception_is_caught_as_failed_partial() -> None:
    run = _build_run(PipelineRunType.COLLECT_PIPELINE)
    executors: dict[PipelineStage, StageExecutor] = dict(_all_completed_executors())
    executors[PipelineStage.PROCESS] = _RaisingExecutor(PipelineStage.PROCESS)
    orch, _ = _orchestrator(run, executors)

    final = await orch.drive(run.id)

    assert final == PipelineRunStatus.PARTIAL
    assert _step(run, PipelineStage.PROCESS).status == PipelineStepStatus.FAILED
    assert "boom" in (_step(run, PipelineStage.PROCESS).error_message or "")


async def test_critical_collect_abort_skips_rest_run_failed() -> None:
    run = _build_run(PipelineRunType.COLLECT_PIPELINE)
    executors = _all_completed_executors()
    executors[PipelineStage.COLLECT] = _CountingExecutor(
        PipelineStage.COLLECT,
        StepResult.failed("hiç kaynak toplanmadı", abort=True),
    )
    orch, _ = _orchestrator(run, dict(executors))

    final = await orch.drive(run.id)

    assert final == PipelineRunStatus.FAILED
    assert run.status == PipelineRunStatus.FAILED
    assert _step(run, PipelineStage.COLLECT).status == PipelineStepStatus.FAILED
    for stage in (PipelineStage.INGEST, PipelineStage.PROCESS, PipelineStage.DIGEST):
        assert _step(run, stage).status == PipelineStepStatus.SKIPPED
    # Abort sonrası executor'lar çağrılmaz
    assert executors[PipelineStage.PROCESS].calls == 0
    assert executors[PipelineStage.DIGEST].calls == 0


async def test_degraded_step_marks_run_partial() -> None:
    run = _build_run(PipelineRunType.COLLECT_PIPELINE)
    executors = _all_completed_executors()
    executors[PipelineStage.COLLECT] = _CountingExecutor(
        PipelineStage.COLLECT,
        StepResult.completed(items_out=3, items_failed=1, degraded=True),
    )
    orch, _ = _orchestrator(run, dict(executors))

    final = await orch.drive(run.id)

    assert final == PipelineRunStatus.PARTIAL
    # Step kendisi completed kalır (step enum'unda partial yok)
    assert _step(run, PipelineStage.COLLECT).status == PipelineStepStatus.COMPLETED


async def test_digest_update_only_runs_digest() -> None:
    run = _build_run(PipelineRunType.DIGEST_UPDATE)
    executors = _all_completed_executors()
    orch, _ = _orchestrator(run, executors)

    final = await orch.drive(run.id)

    assert final == PipelineRunStatus.COMPLETED
    assert _step(run, PipelineStage.DIGEST).status == PipelineStepStatus.COMPLETED
    for stage in DIGEST_UPDATE_SKIPPED:
        assert _step(run, stage).status == PipelineStepStatus.SKIPPED
        assert executors[stage].calls == 0
    assert executors[PipelineStage.DIGEST].calls == 1


async def test_idempotent_redrive_does_not_rerun_completed_steps() -> None:
    run = _build_run(PipelineRunType.COLLECT_PIPELINE)
    executors = _all_completed_executors()
    orch, _ = _orchestrator(run, executors)

    first = await orch.drive(run.id)
    second = await orch.drive(run.id)

    assert first == PipelineRunStatus.COMPLETED
    assert second == PipelineRunStatus.COMPLETED
    # Koşan aşamalar yalnızca ilk drive'da çağrılır; digest (skipped) hiç çağrılmaz.
    for stage in (PipelineStage.COLLECT, PipelineStage.INGEST, PipelineStage.PROCESS):
        assert executors[stage].calls == 1
    assert executors[PipelineStage.DIGEST].calls == 0


async def test_cancelled_run_is_not_driven() -> None:
    run = _build_run(PipelineRunType.COLLECT_PIPELINE)
    run.status = PipelineRunStatus.CANCELLED
    executors = _all_completed_executors()
    orch, _ = _orchestrator(run, executors)

    final = await orch.drive(run.id)

    assert final == PipelineRunStatus.CANCELLED
    assert all(e.calls == 0 for e in executors.values())


async def test_missing_run_returns_failed() -> None:
    orch, _ = _orchestrator(_build_run(PipelineRunType.COLLECT_PIPELINE), {})
    orch._repo = _FakeRunRepository(None)  # type: ignore[assignment]

    final = await orch.drive(uuid.uuid4())

    assert final == PipelineRunStatus.FAILED
