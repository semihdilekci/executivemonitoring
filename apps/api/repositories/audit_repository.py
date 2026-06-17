"""Audit log tablosu veri erişimi."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from packages.shared.models.audit_log import AuditLog
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


class AuditRepository:
    """Audit kayıt oluşturma ve sorgulama."""

    async def get_by_id(self, db: AsyncSession, audit_id: uuid.UUID) -> AuditLog | None:
        result = await db.execute(
            select(AuditLog)
            .options(joinedload(AuditLog.actor))
            .where(AuditLog.id == audit_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        actor_user_id: uuid.UUID | None = None,
        target_type: str | None = None,
        target_id: uuid.UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditLog:
        audit = AuditLog(
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            payload=payload or {},
        )
        db.add(audit)
        await db.flush()
        return audit

    async def list_paginated(
        self,
        db: AsyncSession,
        *,
        cursor: uuid.UUID | None = None,
        limit: int = 20,
        event_type: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        target_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[AuditLog], str | None, bool]:
        """Cursor pagination — sıralama: created_at DESC, id DESC."""
        query: Select[tuple[AuditLog]] = select(AuditLog).options(joinedload(AuditLog.actor))

        if event_type is not None:
            query = query.where(AuditLog.event_type == event_type)
        if actor_user_id is not None:
            query = query.where(AuditLog.actor_user_id == actor_user_id)
        if target_type is not None:
            query = query.where(AuditLog.target_type == target_type)
        if start_date is not None:
            start_dt = datetime.combine(start_date, time.min, tzinfo=UTC)
            query = query.where(AuditLog.created_at >= start_dt)
        if end_date is not None:
            end_exclusive = datetime.combine(
                end_date + timedelta(days=1),
                time.min,
                tzinfo=UTC,
            )
            query = query.where(AuditLog.created_at < end_exclusive)

        if cursor is not None:
            cursor_log = await self.get_by_id(db, cursor)
            if cursor_log is not None:
                query = query.where(
                    or_(
                        AuditLog.created_at < cursor_log.created_at,
                        and_(
                            AuditLog.created_at == cursor_log.created_at,
                            AuditLog.id < cursor_log.id,
                        ),
                    )
                )

        query = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1)
        result = await db.execute(query)
        logs = list(result.scalars().unique().all())

        has_more = len(logs) > limit
        if has_more:
            logs = logs[:limit]

        next_cursor = str(logs[-1].id) if has_more and logs else None
        return logs, next_cursor, has_more
