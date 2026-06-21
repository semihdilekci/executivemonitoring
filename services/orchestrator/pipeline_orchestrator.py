"""Pipeline run state machine — aşamaları ilerleten background driver (Faz 6.1).

`pending → running → completed/partial/failed/cancelled` (`Docs/01` §5.5). Aşamaları
`sequence` sırasında sürer; her geçiş `pipeline_run_steps`'e kalıcılaştırılır ve
**commit edilir** (canlı izleme polling'i ilerlemeyi görsün). Advance idempotenttir:
zaten `completed`/`skipped` step yeniden koşmaz (`Docs/04` §10.5).

Orkestratör kendi DB session'ını `session_factory` ile yönetir — request session'ına
bağlı değildir (background driver). Stage iş mantığı `StageExecutor`'lardadır; bu
sınıf yalnızca durum geçişi + hata politikasıdır.
"""

from __future__ import annotations

import uuid

from packages.shared.enums import PipelineRunStatus, PipelineStage, PipelineStepStatus
from packages.shared.models.pipeline_run import PipelineRun
from packages.shared.models.pipeline_run_step import PipelineRunStep
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from services.orchestrator.run_repository import RunRepository, run_repository
from services.orchestrator.stage_executors import StageExecutor, StepResult

# Yeniden koşulmayacak (terminal/atlanmış) step durumları — idempotency.
_DONE_STEP_STATUSES = frozenset({PipelineStepStatus.COMPLETED, PipelineStepStatus.SKIPPED})


class PipelineOrchestrator:
    """Run'ı state machine olarak ilerleten sürücü."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        executors: dict[PipelineStage, StageExecutor],
        repository: RunRepository = run_repository,
    ) -> None:
        self._session_factory = session_factory
        self._executors = executors
        self._repo = repository

    async def drive(self, run_id: uuid.UUID) -> PipelineRunStatus:
        """Run'ı terminal duruma kadar sür; nihai run durumunu döndür."""
        async with self._session_factory() as db:
            run = await self._repo.get_run(db, run_id)
            if run is None:
                return PipelineRunStatus.FAILED
            # İptal edilmiş run sürülmez; zaten terminal completed/partial/failed
            # re-drive'ında işi tekrar değerlendirir (idempotent).
            if run.status == PipelineRunStatus.CANCELLED:
                return run.status

            await self._repo.mark_run_running(db, run)
            await db.commit()

            final_status = await self._advance_steps(db, run)
            await db.commit()
            return final_status

    async def _advance_steps(self, db: AsyncSession, run: PipelineRun) -> PipelineRunStatus:
        steps = sorted(run.steps, key=lambda s: s.sequence)
        aborted = False
        had_failure = False
        degraded = False
        unexpected: Exception | None = None

        try:
            for step in steps:
                if step.status in _DONE_STEP_STATUSES:
                    continue
                if aborted:
                    await self._repo.skip_step(db, step)
                    await db.commit()
                    continue

                result = await self._execute_step(db, run, step)

                if result.status == PipelineStepStatus.FAILED:
                    if result.abort:
                        aborted = True
                    else:
                        had_failure = True
                elif result.degraded:
                    degraded = True
        except Exception as exc:  # repository/commit hatası — run takılı kalmasın
            unexpected = exc

        final_status = self._resolve_status(
            aborted=aborted,
            had_failure=had_failure,
            degraded=degraded,
            unexpected=unexpected is not None,
        )
        error_summary = self._build_error_summary(steps, unexpected)
        await self._repo.finalize_run(
            db, run, status=final_status, error_summary=error_summary
        )
        if unexpected is not None:
            await db.commit()
            raise unexpected
        return final_status

    async def _execute_step(
        self, db: AsyncSession, run: PipelineRun, step: PipelineRunStep
    ) -> StepResult:
        await self._repo.start_step(db, step)
        await db.commit()
        try:
            result = await self._executors[step.stage].run(run, step)
        except Exception as exc:  # executor çökerse step failed (run partial), abort yok
            result = StepResult.failed(f"{type(exc).__name__}: {exc}")

        await self._repo.advance_step(
            db,
            step,
            status=result.status,
            items_in=result.items_in,
            items_out=result.items_out,
            items_failed=result.items_failed,
            detail=result.detail,
            error=result.error,
        )
        await db.commit()
        return result

    @staticmethod
    def _resolve_status(
        *, aborted: bool, had_failure: bool, degraded: bool, unexpected: bool
    ) -> PipelineRunStatus:
        if unexpected or aborted:
            return PipelineRunStatus.FAILED
        if had_failure or degraded:
            return PipelineRunStatus.PARTIAL
        return PipelineRunStatus.COMPLETED

    @staticmethod
    def _build_error_summary(
        steps: list[PipelineRunStep], unexpected: Exception | None
    ) -> str | None:
        parts = [
            f"{step.stage.value}: {step.error_message}"
            for step in steps
            if step.status == PipelineStepStatus.FAILED and step.error_message
        ]
        if unexpected is not None:
            parts.append(f"orchestrator: {type(unexpected).__name__}: {unexpected}")
        return "; ".join(parts) if parts else None
