"""FastAPI dependency factory fonksiyonları."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from packages.shared.enums import UserRole
from packages.shared.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import ForbiddenException, UnauthorizedException
from apps.api.core.security import decode_jwt

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
