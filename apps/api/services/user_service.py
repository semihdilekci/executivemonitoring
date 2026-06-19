"""Kullanıcı yönetimi iş mantığı."""

from __future__ import annotations

import uuid
from typing import Any

from packages.shared.enums import UserRole
from packages.shared.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import (
    ConflictException,
    NotFoundException,
    PasswordPolicyViolationException,
)
from apps.api.core.security import hash_password, validate_password_strength
from apps.api.repositories.notification_preference_repository import (
    NotificationPreferenceRepository,
)
from apps.api.repositories.user_repository import UserRepository
from apps.api.schemas.common import PaginationMeta
from apps.api.schemas.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)
from apps.api.services.audit_service import AuditService, audit_service

user_repository = UserRepository()
notification_preference_repository = NotificationPreferenceRepository()

_USERS_DEFAULT_LIMIT = 20
_USERS_MAX_LIMIT = 50


def _to_user_response(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


def _validate_password(password: str) -> None:
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise PasswordPolicyViolationException(message=str(exc)) from exc


class UserService:
    """Admin kullanıcı CRUD ve profil okuma."""

    def __init__(
        self,
        users: UserRepository | None = None,
        notification_preferences: NotificationPreferenceRepository | None = None,
        audit_svc: AuditService | None = None,
    ) -> None:
        self._users = users or user_repository
        self._notification_preferences = (
            notification_preferences or notification_preference_repository
        )
        self._audit_service = audit_svc or audit_service

    async def list_users(
        self,
        db: AsyncSession,
        *,
        cursor: str | None = None,
        limit: int = _USERS_DEFAULT_LIMIT,
        role: UserRole | None = None,
        is_active: bool | None = None,
    ) -> UserListResponse:
        resolved_limit = min(max(limit, 1), _USERS_MAX_LIMIT)
        cursor_id: uuid.UUID | None = None
        if cursor is not None:
            try:
                cursor_id = uuid.UUID(cursor)
            except ValueError as exc:
                raise NotFoundException(message="Geçersiz pagination cursor.") from exc

        users, next_cursor, has_more = await self._users.list_paginated(
            db,
            cursor=cursor_id,
            limit=resolved_limit,
            role=role,
            is_active=is_active,
        )
        return UserListResponse(
            data=[_to_user_response(user) for user in users],
            pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more),
        )

    async def get_user(self, db: AsyncSession, user_id: uuid.UUID) -> UserResponse:
        user = await self._users.get_by_id(db, user_id)
        if user is None:
            raise NotFoundException(message="Kullanıcı bulunamadı.")
        return _to_user_response(user)

    async def get_me(self, user: User) -> UserResponse:
        return _to_user_response(user)

    async def create_user(
        self,
        db: AsyncSession,
        *,
        actor: User,
        body: CreateUserRequest,
    ) -> UserResponse:
        _validate_password(body.password)

        existing = await self._users.get_by_email(db, body.email)
        if existing is not None:
            raise ConflictException(
                message="Bu e-posta adresi zaten kayıtlı.",
                error_code="USER_EMAIL_EXISTS",
            )

        user = await self._users.create(
            db,
            email=body.email,
            password_hash=hash_password(body.password),
            full_name=body.full_name,
            role=body.role,
        )
        await self._notification_preferences.create_default(db, user_id=user.id)
        await self._audit_service.log_event(
            db,
            event_type="user.created",
            actor_user_id=actor.id,
            target_type="user",
            target_id=user.id,
            payload={
                "email": user.email,
                "role": user.role.value,
            },
        )
        return _to_user_response(user)

    async def update_user(
        self,
        db: AsyncSession,
        *,
        actor: User,
        user_id: uuid.UUID,
        body: UpdateUserRequest,
    ) -> UserResponse:
        user = await self._users.get_by_id(db, user_id)
        if user is None:
            raise NotFoundException(message="Kullanıcı bulunamadı.")

        if body.full_name is None and body.role is None and body.is_active is None:
            return _to_user_response(user)

        previous_role = user.role
        previous_active = user.is_active

        updated = await self._users.update(
            db,
            user,
            full_name=body.full_name,
            role=body.role,
            is_active=body.is_active,
        )

        await self._write_update_audits(
            db,
            actor=actor,
            user=updated,
            previous_role=previous_role,
            previous_active=previous_active,
            body=body,
        )
        return _to_user_response(updated)

    async def _write_update_audits(
        self,
        db: AsyncSession,
        *,
        actor: User,
        user: User,
        previous_role: UserRole,
        previous_active: bool,
        body: UpdateUserRequest,
    ) -> None:
        if body.role is not None and user.role != previous_role:
            await self._audit_service.log_event(
                db,
                event_type="user.role_changed",
                actor_user_id=actor.id,
                target_type="user",
                target_id=user.id,
                payload={"from": previous_role.value, "to": user.role.value},
            )

        if body.is_active is not None and previous_active and not user.is_active:
            await self._audit_service.log_event(
                db,
                event_type="user.deactivated",
                actor_user_id=actor.id,
                target_type="user",
                target_id=user.id,
                payload={},
            )

        updated_payload: dict[str, Any] = {}
        if body.full_name is not None:
            updated_payload["full_name"] = user.full_name
        if body.is_active is not None and user.is_active != previous_active:
            updated_payload["is_active"] = user.is_active

        if updated_payload:
            await self._audit_service.log_event(
                db,
                event_type="user.updated",
                actor_user_id=actor.id,
                target_type="user",
                target_id=user.id,
                payload=updated_payload,
            )


user_service = UserService()
