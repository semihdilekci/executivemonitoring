"""Digest HTTP endpoint'leri."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from packages.shared.enums import DigestStatus, DigestType
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.deps import (
    get_api_key_service,
    get_api_usage_service,
    get_current_user,
    get_db,
    require_admin,
)
from apps.api.schemas.digest import (
    DigestDetailResponse,
    DigestListResponse,
    GenerateDigestRequest,
    GenerateDigestResponse,
)
from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService
from apps.api.services.digest_service import digest_service

router = APIRouter(prefix="/api/v1/digests", tags=["digests"])


def _get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


@router.get("", response_model=DigestListResponse)
async def list_digests(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    digest_type: Annotated[DigestType | None, Query()] = None,
    status: Annotated[DigestStatus | None, Query()] = None,
) -> DigestListResponse:
    return await digest_service.list_digests(
        db,
        user=user,
        cursor=cursor,
        limit=limit,
        digest_type=digest_type,
        status=status,
    )


@router.get("/{digest_id}", response_model=DigestDetailResponse)
async def get_digest(
    digest_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> DigestDetailResponse:
    return await digest_service.get_digest(db, user=user, digest_id=digest_id)


@router.post(
    "/generate",
    response_model=GenerateDigestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_digest(
    body: GenerateDigestRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
    api_key_service: Annotated[ApiKeyService, Depends(get_api_key_service)],
    api_usage_service: Annotated[ApiUsageService, Depends(get_api_usage_service)],
) -> GenerateDigestResponse:
    return await digest_service.initiate_generation(
        db,
        actor=actor,
        body=body,
        session_factory=_get_session_factory(request),
        api_key_service=api_key_service,
        api_usage_service=api_usage_service,
    )
