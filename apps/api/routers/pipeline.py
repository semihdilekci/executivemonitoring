"""Pipeline monitoring HTTP endpoint'leri — `Docs/03` §11.5 (Faz 6.1).

Tümü admin-only. `POST /runs` trigger rate limit (5/dk) + eşzamanlılık guard ile
asenkron tetikler; ilerleme `GET /runs/{id}` polling ile izlenir.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from packages.shared.enums import PipelineRunStatus, PipelineRunType
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.deps import (
    enforce_pipeline_rate_limit,
    get_api_key_service,
    get_api_usage_service,
    get_db,
    require_admin,
)
from apps.api.schemas.pipeline import (
    CancelPipelineResponse,
    PipelineRunDetail,
    PipelineRunListResponse,
    TriggerPipelineRequest,
    TriggerPipelineResponse,
)
from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService
from apps.api.services.pipeline_service import pipeline_service

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


@router.post(
    "/runs",
    response_model=TriggerPipelineResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_pipeline_run(
    body: TriggerPipelineRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(enforce_pipeline_rate_limit)],
    api_key_service: Annotated[ApiKeyService, Depends(get_api_key_service)],
    api_usage_service: Annotated[ApiUsageService, Depends(get_api_usage_service)],
) -> TriggerPipelineResponse:
    return await pipeline_service.trigger_run(
        db,
        actor=actor,
        body=body,
        session_factory=_get_session_factory(request),
        api_key_service=api_key_service,
        api_usage_service=api_usage_service,
    )


@router.get("/runs", response_model=PipelineRunListResponse)
async def list_pipeline_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    run_type: Annotated[PipelineRunType | None, Query()] = None,
    run_status: Annotated[PipelineRunStatus | None, Query(alias="status")] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> PipelineRunListResponse:
    return await pipeline_service.list_runs(
        db,
        cursor=cursor,
        limit=limit,
        run_type=run_type,
        status=run_status,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/runs/{run_id}", response_model=PipelineRunDetail)
async def get_pipeline_run(
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> PipelineRunDetail:
    return await pipeline_service.get_run(db, run_id=run_id)


@router.post("/runs/{run_id}/cancel", response_model=CancelPipelineResponse)
async def cancel_pipeline_run(
    run_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> CancelPipelineResponse:
    return await pipeline_service.cancel_run(db, actor=actor, run_id=run_id)
