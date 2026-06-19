"""Chat history tablosu veri erişimi."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

from packages.shared.models.chat_history import ChatHistory
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload


class ChatRepository:
    """Chat history CRUD ve listeleme."""

    async def get_by_id(self, db: AsyncSession, history_id: uuid.UUID) -> ChatHistory | None:
        result = await db.execute(
            select(ChatHistory)
            .options(joinedload(ChatHistory.user))
            .where(ChatHistory.id == history_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        question: str,
        answer: str,
        sources: list[dict[str, object]],
        tokens_used: int,
        model: str,
    ) -> ChatHistory:
        row = ChatHistory(
            user_id=user_id,
            question=question,
            answer=answer,
            sources=sources,
            tokens_used=tokens_used,
            model=model,
        )
        db.add(row)
        await db.flush()
        return row

    async def list_paginated(
        self,
        db: AsyncSession,
        *,
        cursor: uuid.UUID | None = None,
        limit: int = 20,
        user_id: uuid.UUID | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> tuple[list[ChatHistory], str | None, bool]:
        """Cursor pagination — sıralama: created_at DESC, id DESC."""
        query: Select[tuple[ChatHistory]] = select(ChatHistory).options(
            joinedload(ChatHistory.user)
        )

        if user_id is not None:
            query = query.where(ChatHistory.user_id == user_id)
        if start_date is not None:
            start_dt = datetime.combine(start_date, time.min, tzinfo=UTC)
            query = query.where(ChatHistory.created_at >= start_dt)
        if end_date is not None:
            end_exclusive = datetime.combine(
                end_date + timedelta(days=1),
                time.min,
                tzinfo=UTC,
            )
            query = query.where(ChatHistory.created_at < end_exclusive)

        if cursor is not None:
            cursor_row = await self.get_by_id(db, cursor)
            if cursor_row is not None:
                query = query.where(
                    or_(
                        ChatHistory.created_at < cursor_row.created_at,
                        and_(
                            ChatHistory.created_at == cursor_row.created_at,
                            ChatHistory.id < cursor_row.id,
                        ),
                    )
                )

        query = query.order_by(ChatHistory.created_at.desc(), ChatHistory.id.desc()).limit(
            limit + 1
        )
        result = await db.execute(query)
        rows = list(result.scalars().unique().all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]

        next_cursor = str(rows[-1].id) if has_more and rows else None
        return rows, next_cursor, has_more


chat_repository = ChatRepository()
