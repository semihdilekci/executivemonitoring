"""Şifre sıfırlama iş mantığı."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import (
    NotFoundException,
    PasswordPolicyViolationException,
    UnauthorizedException,
)
from apps.api.core.security import hash_password, validate_password_strength
from apps.api.repositories.password_reset_repository import PasswordResetRepository
from apps.api.repositories.user_repository import UserRepository
from apps.api.schemas.auth import (
    PasswordResetCompleteResponse,
    PasswordResetInitiateResponse,
)
from apps.api.services.audit_service import AuditService, audit_service
from apps.api.services.email_service import EmailService, email_service

password_reset_repository = PasswordResetRepository()
user_repository = UserRepository()

TOKEN_EXPIRE_HOURS = 24
INVALID_TOKEN_MESSAGE = "Geçersiz veya süresi dolmuş link."


class PasswordResetService:
    """Admin tetiklemeli şifre sıfırlama akışı."""

    def __init__(
        self,
        resets: PasswordResetRepository | None = None,
        users: UserRepository | None = None,
        audit_svc: AuditService | None = None,
        mailer: EmailService | None = None,
    ) -> None:
        self._resets = resets or password_reset_repository
        self._users = users or user_repository
        self._audit_service = audit_svc or audit_service
        self._mailer = mailer or email_service

    async def initiate(
        self,
        db: AsyncSession,
        *,
        actor: User,
        user_id: uuid.UUID,
    ) -> PasswordResetInitiateResponse:
        user = await self._users.get_by_id(db, user_id)
        if user is None:
            raise NotFoundException(message="Kullanıcı bulunamadı.")

        await self._resets.invalidate_active_for_user(db, user_id)

        raw_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(hours=TOKEN_EXPIRE_HOURS)
        await self._resets.create(
            db,
            user_id=user_id,
            token_hash=hash_password(raw_token),
            expires_at=expires_at,
        )
        await self._mailer.send_password_reset_link(email=user.email, raw_token=raw_token)
        await self._audit_service.log_event(
            db,
            event_type="password.reset_initiated",
            actor_user_id=actor.id,
            target_type="user",
            target_id=user.id,
            payload={"email": user.email},
        )
        return PasswordResetInitiateResponse(
            message="Şifre sıfırlama bağlantısı kullanıcıya e-posta ile gönderildi.",
            expires_at=expires_at,
        )

    async def complete(
        self,
        db: AsyncSession,
        *,
        raw_token: str,
        new_password: str,
    ) -> PasswordResetCompleteResponse:
        try:
            validate_password_strength(new_password)
        except ValueError as exc:
            raise PasswordPolicyViolationException(message=str(exc)) from exc

        reset_token = await self._resets.find_valid_by_raw_token(db, raw_token)
        if reset_token is None:
            raise UnauthorizedException(
                message=INVALID_TOKEN_MESSAGE,
                error_code="AUTH_INVALID_RESET_TOKEN",
            )

        user = await self._users.get_by_id(db, reset_token.user_id)
        if user is None:
            raise UnauthorizedException(
                message=INVALID_TOKEN_MESSAGE,
                error_code="AUTH_INVALID_RESET_TOKEN",
            )

        await self._users.update_password_hash(
            db,
            user,
            password_hash=hash_password(new_password),
        )
        await self._resets.mark_used(db, reset_token)
        await self._audit_service.log_event(
            db,
            event_type="password.reset_completed",
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
            payload={},
        )
        return PasswordResetCompleteResponse(message="Şifre başarıyla güncellendi.")


password_reset_service = PasswordResetService()
