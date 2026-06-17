"""Kimlik doğrulama HTTP endpoint'leri."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import get_current_user, get_db, require_admin
from apps.api.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    PasswordResetCompleteRequest,
    PasswordResetCompleteResponse,
    PasswordResetInitiateRequest,
    PasswordResetInitiateResponse,
    RefreshRequest,
    RefreshResponse,
)
from apps.api.services.auth_service import auth_service
from apps.api.services.password_reset_service import password_reset_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    return await auth_service.login(
        db,
        email=body.email,
        password=body.password,
        client_ip=_client_ip(request),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RefreshResponse:
    return await auth_service.refresh(db, refresh_token=body.refresh_token)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> LogoutResponse:
    return await auth_service.logout(db, user=current_user)


@router.post("/password-reset/initiate", response_model=PasswordResetInitiateResponse)
async def initiate_password_reset(
    body: PasswordResetInitiateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[User, Depends(require_admin)],
) -> PasswordResetInitiateResponse:
    return await password_reset_service.initiate(db, actor=actor, user_id=body.user_id)


@router.post("/password-reset/complete", response_model=PasswordResetCompleteResponse)
async def complete_password_reset(
    body: PasswordResetCompleteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PasswordResetCompleteResponse:
    return await password_reset_service.complete(
        db,
        raw_token=body.token,
        new_password=body.new_password,
    )
