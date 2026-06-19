"""LLM API key yönetimi HTTP endpoint'leri."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from packages.shared.enums import ApiProvider
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import (
    get_api_key_service,
    get_api_usage_service,
    get_db,
    require_admin,
)
from apps.api.schemas.api_key import (
    ApiKeyListResponse,
    ApiKeyResponse,
    ApiUsageStatsResponse,
    CreateApiKeyRequest,
    DeleteApiKeyResponse,
    PatchApiKeyStatusRequest,
)
from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    service: Annotated[ApiKeyService, Depends(get_api_key_service)],
) -> ApiKeyListResponse:
    return await service.list_api_keys(db)


@router.post("", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateApiKeyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
    service: Annotated[ApiKeyService, Depends(get_api_key_service)],
) -> ApiKeyResponse:
    return await service.create_api_key(db, actor=actor, body=body)


@router.delete("/{key_id}", response_model=DeleteApiKeyResponse)
async def delete_api_key(
    key_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
    service: Annotated[ApiKeyService, Depends(get_api_key_service)],
) -> DeleteApiKeyResponse:
    return await service.delete_api_key(db, actor=actor, key_id=key_id)


@router.patch("/{key_id}/status", response_model=ApiKeyResponse)
async def patch_api_key_status(
    key_id: UUID,
    body: PatchApiKeyStatusRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
    service: Annotated[ApiKeyService, Depends(get_api_key_service)],
) -> ApiKeyResponse:
    return await service.patch_api_key_status(
        db,
        actor=actor,
        key_id=key_id,
        body=body,
    )


@router.get("/usage-stats", response_model=ApiUsageStatsResponse)
async def get_api_usage_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    service: Annotated[ApiUsageService, Depends(get_api_usage_service)],
    period: Annotated[Literal["daily", "weekly", "monthly"], Query()] = "daily",
    provider: Annotated[ApiProvider | None, Query()] = None,
    api_key_id: Annotated[UUID | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> ApiUsageStatsResponse:
    return await service.get_usage_stats(
        db,
        period=period,
        provider=provider,
        api_key_id=api_key_id,
        start_date=start_date,
        end_date=end_date,
    )
