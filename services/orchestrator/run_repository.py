"""Pipeline run / step veri erişimi + transaction'lı durum geçişleri (Faz 6.1).

Tek entity sorumluluğu (`Docs/04` §6): yalnızca `pipeline_runs` ve onun
`pipeline_run_steps` alt kayıtlarına erişir. İş mantığı (state machine) orkestratörde;
burada yalnızca CRUD + atomik geçiş + sayaç yazımı. Raw SQL yok (`03-security-baseline`).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from packages.shared.enums import (
    PipelineRunStatus,
    PipelineRunType,
    PipelineStage,
    PipelineStepStatus,
)
from packages.shared.models.pipeline_run import PipelineRun
from packages.shared.models.pipeline_run_step import PipelineRunStep
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

# Aşama → sequence (sabit yürütme sırası, `Docs/01` §5.5)
STAGE_SEQUENCE: dict[PipelineStage, int] = {
    PipelineStage.COLLECT: 1,
    PipelineStage.INGEST: 2,
    PipelineStage.PROCESS: 3,
    PipelineStage.DIGEST: 4,
}

# `digest_update` run'ında yalnızca digest koşar; diğerleri baştan `skipped`.
DIGEST_UPDATE_SKIPPED: frozenset[PipelineStage] = frozenset(
    {PipelineStage.COLLECT, PipelineStage.INGEST, PipelineStage.PROCESS}
)

# `collect_pipeline` yalnızca collect→ingest→process koşar; bülten ayrı `digest_update`
# run'ıyla üretilir (`Docs/03` §7 — digest parametreleri yalnızca digest_update'te).
COLLECT_PIPELINE_SKIPPED: frozenset[PipelineStage] = frozenset({PipelineStage.DIGEST})


def _skipped_stages(run_type: PipelineRunType) -> frozenset[PipelineStage]:
    """Run tipine göre baştan `skipped` işaretlenecek aşamalar."""
    if run_type == PipelineRunType.DIGEST_UPDATE:
        return DIGEST_UPDATE_SKIPPED
    if run_type == PipelineRunType.COLLECT_PIPELINE:
        return COLLECT_PIPELINE_SKIPPED
    return frozenset()


def _now() -> datetime:
    return datetime.now(UTC)


class RunRepository:
    """`pipeline_runs` / `pipeline_run_steps` CRUD ve durum geçişleri."""

    async def create_run(
        self,
        db: AsyncSession,
        *,
        run_type: PipelineRunType,
        source_types: list[str],
        params: dict[str, Any] | None = None,
        triggered_by: uuid.UUID | None = None,
    ) -> PipelineRun:
        run = PipelineRun(
            run_type=run_type,
            status=PipelineRunStatus.PENDING,
            source_types=source_types,
            params=params or {},
            stats={},
            triggered_by=triggered_by,
        )
        db.add(run)
        await db.flush()
        return run

    async def init_steps(self, db: AsyncSession, run: PipelineRun) -> list[PipelineRunStep]:
        """4 aşamayı `sequence` sırasıyla oluştur.

        `digest_update`'te collect/ingest/process baştan `skipped`, digest `pending`;
        `collect_pipeline`'da digest baştan `skipped` (bülten ayrı digest_update ile
        üretilir), diğerleri `pending` (`Docs/01` §5.5, `Docs/03` §7).
        """
        skipped_stages = _skipped_stages(run.run_type)
        steps: list[PipelineRunStep] = []
        for stage, sequence in STAGE_SEQUENCE.items():
            skipped = stage in skipped_stages
            step = PipelineRunStep(
                run_id=run.id,
                stage=stage,
                sequence=sequence,
                status=PipelineStepStatus.SKIPPED if skipped else PipelineStepStatus.PENDING,
            )
            db.add(step)
            steps.append(step)
        await db.flush()
        return steps

    async def get_run(self, db: AsyncSession, run_id: uuid.UUID) -> PipelineRun | None:
        result = await db.execute(
            select(PipelineRun)
            .options(
                selectinload(PipelineRun.steps),
                selectinload(PipelineRun.triggered_by_user),
            )
            .where(PipelineRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def has_active_run(
        self, db: AsyncSession, run_type: PipelineRunType
    ) -> bool:
        """Aynı tipte `pending`/`running` bir run var mı (eşzamanlılık guard, `Docs/03` §11.5)."""
        result = await db.execute(
            select(PipelineRun.id)
            .where(
                PipelineRun.run_type == run_type,
                PipelineRun.status.in_(
                    (PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING)
                ),
            )
            .limit(1)
        )
        return result.first() is not None

    async def list_paginated(
        self,
        db: AsyncSession,
        *,
        cursor: uuid.UUID | None = None,
        limit: int = 20,
        run_type: PipelineRunType | None = None,
        status: PipelineRunStatus | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[PipelineRun], str | None, bool]:
        """Run geçmişi — `created_at DESC, id DESC` cursor pagination (`Docs/03` §14).

        Yalnızca okuma; step'leri de eager yükler (liste mini step göstergesi için).
        """
        stmt = select(PipelineRun).options(
            selectinload(PipelineRun.steps),
            selectinload(PipelineRun.triggered_by_user),
        )
        if run_type is not None:
            stmt = stmt.where(PipelineRun.run_type == run_type)
        if status is not None:
            stmt = stmt.where(PipelineRun.status == status)
        if start_date is not None:
            stmt = stmt.where(PipelineRun.created_at >= start_date)
        if end_date is not None:
            stmt = stmt.where(PipelineRun.created_at <= end_date)
        if cursor is not None:
            anchor = await db.get(PipelineRun, cursor)
            if anchor is not None:
                stmt = stmt.where(
                    tuple_(PipelineRun.created_at, PipelineRun.id)
                    < (anchor.created_at, anchor.id)
                )
        stmt = stmt.order_by(
            PipelineRun.created_at.desc(), PipelineRun.id.desc()
        ).limit(limit + 1)

        rows = list((await db.execute(stmt)).scalars().all())
        has_more = len(rows) > limit
        page = rows[:limit]
        next_cursor = str(page[-1].id) if has_more and page else None
        return page, next_cursor, has_more

    async def mark_run_running(self, db: AsyncSession, run: PipelineRun) -> None:
        run.status = PipelineRunStatus.RUNNING
        if run.started_at is None:
            run.started_at = _now()
        await db.flush()

    async def start_step(self, db: AsyncSession, step: PipelineRunStep) -> None:
        step.status = PipelineStepStatus.RUNNING
        if step.started_at is None:
            step.started_at = _now()
        await db.flush()

    async def advance_step(
        self,
        db: AsyncSession,
        step: PipelineRunStep,
        *,
        status: PipelineStepStatus,
        items_in: int = 0,
        items_out: int = 0,
        items_failed: int = 0,
        detail: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Bir step'i terminal duruma (`completed`/`failed`) sayaçlarıyla kapat."""
        step.status = status
        step.items_in = items_in
        step.items_out = items_out
        step.items_failed = items_failed
        step.detail = detail or {}
        step.error_message = error
        step.finished_at = _now()
        await db.flush()

    async def skip_step(self, db: AsyncSession, step: PipelineRunStep) -> None:
        """Kritik hata sonrası koşmayan step'i `skipped` işaretle."""
        step.status = PipelineStepStatus.SKIPPED
        step.finished_at = _now()
        await db.flush()

    async def finalize_run(
        self,
        db: AsyncSession,
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
        run.finished_at = _now()
        await db.flush()


run_repository = RunRepository()
