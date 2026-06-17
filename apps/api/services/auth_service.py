"""Kimlik doğrulama iş mantığı."""

from __future__ import annotations

import uuid
from typing import Any

from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import Settings, get_settings
from apps.api.core.exceptions import ForbiddenException, UnauthorizedException
from apps.api.core.security import (
    access_token_expires_in_seconds,
    create_access_token,
    create_refresh_token,
    decode_jwt,
    verify_password,
)
from apps.api.repositories.user_repository import UserRepository
from apps.api.schemas.auth import LoginResponse, LogoutResponse, RefreshResponse, UserAuthResponse
from apps.api.services.audit_service import AuditService, audit_service
from apps.api.services.settings_service import SettingsService, settings_service

user_repository = UserRepository()


def _to_user_auth_response(user: User) -> UserAuthResponse:
    return UserAuthResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


async def _build_login_response(
    db: AsyncSession,
    user: User,
    *,
    app_settings: Settings,
    settings_svc: SettingsService,
) -> LoginResponse:
    access_minutes = await settings_svc.get_jwt_access_token_minutes(db)
    refresh_days = await settings_svc.get_jwt_refresh_token_days(db)
    access_token = create_access_token(
        str(user.id),
        user.role.value,
        user.email,
        settings=app_settings,
        expire_minutes=access_minutes,
    )
    refresh_token = create_refresh_token(
        str(user.id),
        settings=app_settings,
        expire_days=refresh_days,
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_token_expires_in_seconds(
            app_settings,
            expire_minutes=access_minutes,
        ),
        user=_to_user_auth_response(user),
    )


class AuthService:
    """Login, refresh ve logout akışları."""

    def __init__(
        self,
        users: UserRepository | None = None,
        audit_svc: AuditService | None = None,
        settings: Settings | None = None,
        settings_svc: SettingsService | None = None,
    ) -> None:
        self._users = users or user_repository
        self._audit_service = audit_svc or audit_service
        self._settings = settings or get_settings()
        self._settings_service = settings_svc or settings_service

    async def _record_failed_login(
        self,
        db: AsyncSession,
        *,
        email: str,
        client_ip: str,
        target_id: uuid.UUID | None = None,
        extra_payload: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"ip": client_ip, "email_attempted": email}
        if extra_payload:
            payload.update(extra_payload)
        await self._audit_service.log_event(
            db,
            event_type="user.login_failed",
            actor_user_id=None,
            target_type="user" if target_id else None,
            target_id=target_id,
            payload=payload,
        )
        await db.commit()

    async def login(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str,
        client_ip: str,
    ) -> LoginResponse:
        user = await self._users.get_by_email(db, email)

        if user is None or not verify_password(password, user.password_hash):
            await self._record_failed_login(db, email=email, client_ip=client_ip)
            raise UnauthorizedException(
                message="E-posta veya şifre hatalı.",
                error_code="AUTH_INVALID_CREDENTIALS",
            )

        if not user.is_active:
            await self._record_failed_login(
                db,
                email=email,
                client_ip=client_ip,
                target_id=user.id,
                extra_payload={"reason": "inactive"},
            )
            raise ForbiddenException(
                message="Kullanıcı hesabı pasif.",
                error_code="AUTH_ACCOUNT_INACTIVE",
            )

        await self._users.update_last_login(db, user)
        await self._audit_service.log_event(
            db,
            event_type="user.login",
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
            payload={"ip": client_ip},
        )
        return await _build_login_response(
            db,
            user,
            app_settings=self._settings,
            settings_svc=self._settings_service,
        )

    async def refresh(self, db: AsyncSession, *, refresh_token: str) -> RefreshResponse:
        payload = decode_jwt(refresh_token, expected_type="refresh", settings=self._settings)
        user_id = uuid.UUID(payload["sub"])
        user = await self._users.get_by_id(db, user_id)

        if user is None:
            raise UnauthorizedException(
                message="Geçersiz token.",
                error_code="AUTH_INVALID_REFRESH_TOKEN",
            )

        if not user.is_active:
            raise ForbiddenException(
                message="Kullanıcı hesabı pasif.",
                error_code="AUTH_ACCOUNT_INACTIVE",
            )

        access_minutes = await self._settings_service.get_jwt_access_token_minutes(db)
        access_token = create_access_token(
            str(user.id),
            user.role.value,
            user.email,
            settings=self._settings,
            expire_minutes=access_minutes,
        )
        return RefreshResponse(
            access_token=access_token,
            expires_in=access_token_expires_in_seconds(
                self._settings,
                expire_minutes=access_minutes,
            ),
        )

    async def logout(self, db: AsyncSession, *, user: User) -> LogoutResponse:
        await self._audit_service.log_event(
            db,
            event_type="user.logout",
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
            payload={},
        )
        return LogoutResponse(message="Oturum sonlandırıldı.")


auth_service = AuthService()
