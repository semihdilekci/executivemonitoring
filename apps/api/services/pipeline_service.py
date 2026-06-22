"""Pipeline monitoring iş mantığı — tetik/list/detay/iptal (Faz 6.1).

Tetikleme asenkron: run + step'ler `pending` oluşturulur, audit yazılır ve commit
edilir; ardından **background driver** (orkestratör) ayrı `session_factory` ile aşamaları
sürer (`Docs/04` §10.5 — request lifecycle'ından bağımsız). Driver testlerde no-op'a
override edilir (gerçek AWS invoke / LLM çağrısı yok). Tüm endpoint'ler admin-only;
audit `pipeline.*` aynı transaction'da (`Docs/07` §9.1).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Any

from packages.shared.enums import (
    PipelineRunStatus,
    PipelineRunType,
    PipelineStage,
    PipelineStepStatus,
)
from packages.shared.models.pipeline_run import PipelineRun
from packages.shared.models.user import User
from services.orchestrator.run_repository import RunRepository, run_repository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.exceptions import (
    InvalidSourceTypeException,
    NotFoundException,
    PipelineAlreadyRunningException,
    PipelineNotCancellableException,
)
from apps.api.repositories.pipeline_items_repository import (
    ItemOutcome,
    pipeline_items_repository,
)
from apps.api.schemas.common import PaginationMeta
from apps.api.schemas.pipeline import (
    CancelPipelineResponse,
    PipelineRunDetail,
    PipelineRunListResponse,
    PipelineRunSummary,
    PipelineStepResponse,
    RunItemResponse,
    RunItemsResponse,
    RunSourceBreakdownResponse,
    TriggerPipelineRequest,
    TriggerPipelineResponse,
)
from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService
from apps.api.services.audit_service import AuditService, audit_service

logger = logging.getLogger("ygip.api.pipeline_service")

_PIPELINE_DEFAULT_LIMIT = 20
_PIPELINE_MAX_LIMIT = 50

# İzinli `source_types` değerleri — `all` aktif tiplere genişler (`Docs/03` §11.5).
_ALLOWED_SOURCE_TYPES: frozenset[str] = frozenset({"rss", "email", "gov", "all"})
_TERMINAL_RUN_STATUSES: frozenset[PipelineRunStatus] = frozenset(
    {
        PipelineRunStatus.COMPLETED,
        PipelineRunStatus.PARTIAL,
        PipelineRunStatus.FAILED,
        PipelineRunStatus.CANCELLED,
    }
)

# (run_id, session_factory, api_key_service, api_usage_service) -> None
RunDriver = Callable[..., Awaitable[None]]


def _current_stage(run: PipelineRun) -> PipelineStage | None:
    """`running` durumdaki run için o an koşan aşama; aksi halde `None` (`Docs/03` §11.5)."""
    if run.status != PipelineRunStatus.RUNNING:
        return None
    for step in sorted(run.steps, key=lambda s: s.sequence):
        if step.status == PipelineStepStatus.RUNNING:
            return step.stage
    return None


def _triggered_by_name(run: PipelineRun) -> str | None:
    user = run.triggered_by_user
    return user.full_name if user is not None else None


def _to_summary(run: PipelineRun) -> PipelineRunSummary:
    return PipelineRunSummary(
        id=run.id,
        run_type=run.run_type,
        status=run.status,
        source_types=list(run.source_types or []),
        stats=dict(run.stats or {}),
        triggered_by_name=_triggered_by_name(run),
        current_stage=_current_stage(run),
        started_at=run.started_at,
        finished_at=run.finished_at,
        created_at=run.created_at,
    )


def _to_detail(run: PipelineRun) -> PipelineRunDetail:
    steps = [
        PipelineStepResponse.model_validate(step)
        for step in sorted(run.steps, key=lambda s: s.sequence)
    ]
    return PipelineRunDetail(
        **_to_summary(run).model_dump(),
        params=dict(run.params or {}),
        error_summary=run.error_summary,
        steps=steps,
    )


class PipelineService:
    """Pipeline run tetikleme, listeleme, detay ve iptal."""

    def __init__(
        self,
        *,
        runs: RunRepository | None = None,
        audit_svc: AuditService | None = None,
        run_driver: RunDriver | None = None,
    ) -> None:
        self._runs = runs or run_repository
        self._audit_service = audit_svc or audit_service
        self._run_driver = run_driver

    async def trigger_run(
        self,
        db: AsyncSession,
        *,
        actor: User,
        body: TriggerPipelineRequest,
        session_factory: async_sessionmaker[AsyncSession],
        api_key_service: ApiKeyService,
        api_usage_service: ApiUsageService,
    ) -> TriggerPipelineResponse:
        source_types = self._resolve_source_types(body)
        params = self._resolve_params(body)

        if await self._runs.has_active_run(db, body.run_type):
            raise PipelineAlreadyRunningException()

        run = await self._runs.create_run(
            db,
            run_type=body.run_type,
            source_types=source_types,
            params=params,
            triggered_by=actor.id,
        )
        await self._runs.init_steps(db, run)
        await self._audit_service.log_event(
            db,
            event_type="pipeline.triggered",
            actor_user_id=actor.id,
            target_type="pipeline_run",
            target_id=run.id,
            payload={
                "run_type": body.run_type.value,
                "source_types": source_types,
                "params": params,
            },
        )
        run_id = run.id
        # Driver ayrı session'da run'ı id ile okur — önce commit et ki görünsün.
        await db.commit()

        driver = self._run_driver or self._default_run_driver
        await driver(
            run_id=run_id,
            session_factory=session_factory,
            api_key_service=api_key_service,
            api_usage_service=api_usage_service,
        )

        return TriggerPipelineResponse(
            id=run_id,
            run_type=body.run_type,
            status=PipelineRunStatus.PENDING,
        )

    async def list_runs(
        self,
        db: AsyncSession,
        *,
        cursor: str | None = None,
        limit: int = _PIPELINE_DEFAULT_LIMIT,
        run_type: PipelineRunType | None = None,
        status: PipelineRunStatus | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> PipelineRunListResponse:
        resolved_limit = min(max(limit, 1), _PIPELINE_MAX_LIMIT)
        cursor_id = self._parse_cursor(cursor)
        runs, next_cursor, has_more = await self._runs.list_paginated(
            db,
            cursor=cursor_id,
            limit=resolved_limit,
            run_type=run_type,
            status=status,
            start_date=_as_datetime(start_date),
            end_date=_as_datetime(end_date, end_of_day=True),
        )
        return PipelineRunListResponse(
            data=[_to_summary(run) for run in runs],
            pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more),
        )

    async def get_run(
        self,
        db: AsyncSession,
        *,
        run_id: uuid.UUID,
    ) -> PipelineRunDetail:
        run = await self._runs.get_run(db, run_id)
        if run is None:
            raise NotFoundException(
                message="Pipeline çalıştırması bulunamadı.",
                error_code="PIPELINE_RUN_NOT_FOUND",
            )
        return _to_detail(run)

    async def get_run_items(
        self,
        db: AsyncSession,
        *,
        run_id: uuid.UUID,
        outcome: ItemOutcome | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> RunItemsResponse:
        """Run penceresindeki okunan/işlenen/elenen içerik kırılımı (`Docs/04` §8.3)."""
        run = await self._runs.get_run(db, run_id)
        if run is None:
            raise NotFoundException(
                message="Pipeline çalıştırması bulunamadı.",
                error_code="PIPELINE_RUN_NOT_FOUND",
            )
        result = await pipeline_items_repository.get_run_items(
            db, run=run, outcome=outcome, page=page, page_size=page_size
        )
        return RunItemsResponse(
            collected=result.collected,
            processed=result.processed,
            filtered=result.filtered,
            failed=result.failed,
            by_source=[
                RunSourceBreakdownResponse.model_validate(item)
                for item in result.by_source
            ],
            items=[RunItemResponse.model_validate(item) for item in result.items],
            page=page,
            page_size=page_size,
            total=result.total,
        )

    async def cancel_run(
        self,
        db: AsyncSession,
        *,
        actor: User,
        run_id: uuid.UUID,
    ) -> CancelPipelineResponse:
        run = await self._runs.get_run(db, run_id)
        if run is None:
            raise NotFoundException(
                message="Pipeline çalıştırması bulunamadı.",
                error_code="PIPELINE_RUN_NOT_FOUND",
            )
        if run.status in _TERMINAL_RUN_STATUSES:
            raise PipelineNotCancellableException()

        await self._runs.finalize_run(db, run, status=PipelineRunStatus.CANCELLED)
        await self._audit_service.log_event(
            db,
            event_type="pipeline.cancelled",
            actor_user_id=actor.id,
            target_type="pipeline_run",
            target_id=run.id,
            payload={"run_type": run.run_type.value},
        )
        return CancelPipelineResponse(id=run.id, status=PipelineRunStatus.CANCELLED)

    def _resolve_source_types(self, body: TriggerPipelineRequest) -> list[str]:
        if body.run_type != PipelineRunType.COLLECT_PIPELINE:
            return []
        requested = body.source_types or []
        invalid = [value for value in requested if value not in _ALLOWED_SOURCE_TYPES]
        if invalid:
            raise InvalidSourceTypeException(
                message="Geçersiz kaynak tipi: " + ", ".join(invalid),
                details={"invalid": invalid, "allowed": sorted(_ALLOWED_SOURCE_TYPES)},
            )
        # "all" verildiyse tek başına yeterli — genişleme orkestratörde yapılır.
        if "all" in requested:
            return ["all"]
        # Sırayı koru, tekrarı temizle.
        seen: dict[str, None] = {}
        for value in requested:
            seen.setdefault(value, None)
        return list(seen)

    @staticmethod
    def _resolve_params(body: TriggerPipelineRequest) -> dict[str, Any]:
        if body.run_type != PipelineRunType.DIGEST_UPDATE:
            return {}
        assert body.digest_type is not None  # model_validator garanti eder
        assert body.period_start is not None
        assert body.period_end is not None
        return {
            "digest_type": body.digest_type.value,
            "period_start": body.period_start.isoformat(),
            "period_end": body.period_end.isoformat(),
            "send_notification": body.send_notification,
        }

    @staticmethod
    def _parse_cursor(cursor: str | None) -> uuid.UUID | None:
        if cursor is None:
            return None
        try:
            return uuid.UUID(cursor)
        except ValueError as exc:
            raise NotFoundException(message="Geçersiz pagination cursor.") from exc

    async def _default_run_driver(
        self,
        *,
        run_id: uuid.UUID,
        session_factory: async_sessionmaker[AsyncSession],
        api_key_service: ApiKeyService,
        api_usage_service: ApiUsageService,
    ) -> None:
        """Orkestratörü gerçek aşama executor'larıyla kurup arka planda sürer.

        `apps/api` LLM/key servisleri yalnızca burada bağlanır; orkestratör paketi
        `apps/api`'ye bağımlı kalmaz (digest generator_factory enjeksiyonu).
        """
        from apps.api.services.pipeline_driver import schedule_pipeline_run

        asyncio.create_task(
            schedule_pipeline_run(
                run_id=run_id,
                session_factory=session_factory,
                api_key_service=api_key_service,
                api_usage_service=api_usage_service,
                audit_service=self._audit_service,
            )
        )


def _as_datetime(value: date | None, *, end_of_day: bool = False) -> datetime | None:
    if value is None:
        return None
    if end_of_day:
        return datetime(value.year, value.month, value.day, 23, 59, 59, 999999)
    return datetime(value.year, value.month, value.day)


pipeline_service = PipelineService()
