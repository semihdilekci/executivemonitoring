"""Audit log iş mantığı."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from packages.shared.models.audit_log import AuditLog
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.exceptions import NotFoundException
from apps.api.repositories.audit_repository import AuditRepository
from apps.api.schemas.audit import AuditLogListResponse, AuditLogResponse
from apps.api.schemas.common import PaginationMeta

audit_repository = AuditRepository()

_AUDIT_DEFAULT_LIMIT = 20
_AUDIT_MAX_LIMIT = 100

_SENSITIVE_PAYLOAD_KEYS = frozenset(
    {
        "password",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "secret",
    }
)


def _sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    return {
        key: value for key, value in payload.items() if key.lower() not in _SENSITIVE_PAYLOAD_KEYS
    }


def _to_audit_response(log: AuditLog) -> AuditLogResponse:
    actor_name = log.actor.full_name if log.actor is not None else None
    return AuditLogResponse(
        id=log.id,
        event_type=log.event_type,
        actor_user_id=log.actor_user_id,
        actor_name=actor_name,
        target_type=log.target_type,
        target_id=log.target_id,
        payload=log.payload,
        created_at=log.created_at,
    )


class AuditService:
    """Audit yazımı ve admin listeleme."""

    def __init__(self, audits: AuditRepository | None = None) -> None:
        self._audits = audits or audit_repository

    async def log_event(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        actor_user_id: uuid.UUID | None = None,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Flush only — commit get_db transaction boundary'sinde."""
        return await self._audits.create(
            db,
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            payload=_sanitize_payload(payload),
        )

    async def list_audit_logs(
        self,
        db: AsyncSession,
        *,
        cursor: str | None = None,
        limit: int = _AUDIT_DEFAULT_LIMIT,
        event_type: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        target_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AuditLogListResponse:
        resolved_limit = min(max(limit, 1), _AUDIT_MAX_LIMIT)
        cursor_id: uuid.UUID | None = None
        if cursor is not None:
            try:
                cursor_id = uuid.UUID(cursor)
            except ValueError as exc:
                raise NotFoundException(message="Geçersiz pagination cursor.") from exc

        logs, next_cursor, has_more = await self._audits.list_paginated(
            db,
            cursor=cursor_id,
            limit=resolved_limit,
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_type=target_type,
            start_date=start_date,
            end_date=end_date,
        )
        return AuditLogListResponse(
            data=[_to_audit_response(log) for log in logs],
            pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more),
        )


audit_service = AuditService()
