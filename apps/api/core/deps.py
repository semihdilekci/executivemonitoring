"""FastAPI dependency factory fonksiyonları."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from packages.shared.enums import UserRole
from packages.shared.models.user import User
from services.ai_engine.llm_client import LLMClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import Settings, get_settings
from apps.api.core.exceptions import ForbiddenException, RateLimitException, UnauthorizedException
from apps.api.core.security import decode_jwt
from apps.api.middleware.rate_limiter import (
    WINDOW_SECONDS,
    RateLimiterBackend,
    build_rate_limit_key,
    create_rate_limiter_backend,
)
from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService
from apps.api.services.llm_client_factory import build_llm_client

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Request başına tek async session; commit/rollback otomatik."""
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise UnauthorizedException(
            message="Kimlik doğrulama gerekli.",
            error_code="UNAUTHORIZED",
        )

    payload = decode_jwt(credentials.credentials, expected_type="access")
    user_id = UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise UnauthorizedException(
            message="Geçersiz token.",
            error_code="AUTH_TOKEN_INVALID",
        )
    if not user.is_active:
        raise ForbiddenException(
            message="Kullanıcı hesabı pasif.",
            error_code="AUTH_ACCOUNT_INACTIVE",
        )
    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenException(
            message="Bu işlem için yönetici yetkisi gereklidir.",
        )
    return current_user


def require_role(role: UserRole) -> Callable[..., User]:
    """Belirli rol veya admin erişimi için guard factory."""

    async def guard(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role != role and current_user.role != UserRole.ADMIN:
            raise ForbiddenException(message="Bu işlem için yetkiniz yok.")
        return current_user

    return guard  # type: ignore[return-value]


require_authenticated = get_current_user


def get_api_key_service(request: Request) -> ApiKeyService:
    """Request app state üzerinden settings-aware API key servisi."""
    service = getattr(request.app.state, "api_key_service", None)
    if isinstance(service, ApiKeyService):
        return service
    settings = getattr(request.app.state, "settings", None) or get_settings()
    return ApiKeyService(settings=settings)


def get_api_usage_service(request: Request) -> ApiUsageService:
    """Request app state üzerinden API usage servisi."""
    service = getattr(request.app.state, "api_usage_service", None)
    if isinstance(service, ApiUsageService):
        return service
    return ApiUsageService()


async def get_llm_client(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_key_service: Annotated[ApiKeyService, Depends(get_api_key_service)],
    api_usage_service: Annotated[ApiUsageService, Depends(get_api_usage_service)],
) -> LLMClient:
    """DB aktif key'ler + usage hook ile request-scoped LLM client."""
    return await build_llm_client(db, api_key_service, api_usage_service)


def _resolve_rate_limiter_backend(request: Request) -> RateLimiterBackend:
    backend = getattr(request.app.state, "rate_limiter_backend", None)
    if isinstance(backend, RateLimiterBackend):
        return backend
    settings = getattr(request.app.state, "settings", None) or get_settings()
    return create_rate_limiter_backend(settings)


async def enforce_chat_rate_limit(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Chatbot endpoint per-user rate limit — `Docs/03` §15 (20 req/dk)."""
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    request.state.user_id = str(user.id)
    key = build_rate_limit_key("chatbot", request)
    backend = _resolve_rate_limiter_backend(request)
    exceeded, retry_after = await backend.increment_and_check(
        key,
        settings.RATE_LIMIT_CHATBOT,
        WINDOW_SECONDS,
    )
    if exceeded:
        raise RateLimitException(retry_after_seconds=retry_after)
    return user
