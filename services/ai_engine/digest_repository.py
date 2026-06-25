"""Digest tablosu veri erişimi."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from packages.shared.enums import DigestStatus
from packages.shared.models.digest import Digest
from packages.shared.models.digest_section import DigestSection
from sqlalchemy import Select, and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class DigestRepository:
    """Digest CRUD ve idempotent dönem sorgusu."""

    async def get_by_id(self, db: AsyncSession, digest_id: uuid.UUID) -> Digest | None:
        result = await db.execute(
            select(Digest)
            .options(selectinload(Digest.sections))
            .where(Digest.id == digest_id)
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        db: AsyncSession,
        *,
        cursor: uuid.UUID | None = None,
        limit: int = 10,
        newsletter_slug: str | None = None,
        status: DigestStatus | None = None,
    ) -> tuple[list[Digest], str | None, bool]:
        """Cursor pagination — sıralama: created_at DESC, id DESC."""
        query: Select[tuple[Digest]] = select(Digest)

        if newsletter_slug is not None:
            query = query.where(Digest.newsletter_slug == newsletter_slug)
        if status is not None:
            query = query.where(Digest.status == status)

        if cursor is not None:
            cursor_digest = await self.get_by_id(db, cursor)
            if cursor_digest is not None:
                query = query.where(
                    or_(
                        Digest.created_at < cursor_digest.created_at,
                        and_(
                            Digest.created_at == cursor_digest.created_at,
                            Digest.id < cursor_digest.id,
                        ),
                    )
                )

        query = query.order_by(Digest.created_at.desc(), Digest.id.desc()).limit(limit + 1)
        result = await db.execute(query)
        digests = list(result.scalars().all())

        has_more = len(digests) > limit
        if has_more:
            digests = digests[:limit]

        next_cursor = str(digests[-1].id) if has_more and digests else None
        return digests, next_cursor, has_more

    async def find_for_period(
        self,
        db: AsyncSession,
        *,
        newsletter_slug: str,
        period_start: date,
        period_end: date,
    ) -> Digest | None:
        result = await db.execute(
            select(Digest).where(
                Digest.newsletter_slug == newsletter_slug,
                Digest.period_start == period_start,
                Digest.period_end == period_end,
            )
        )
        return result.scalar_one_or_none()

    async def create_generating(
        self,
        db: AsyncSession,
        *,
        newsletter_slug: str,
        newsletter_template_id: uuid.UUID | None,
        title: str,
        period_start: date,
        period_end: date,
    ) -> Digest:
        digest = Digest(
            newsletter_slug=newsletter_slug,
            newsletter_template_id=newsletter_template_id,
            title=title,
            status=DigestStatus.GENERATING,
            period_start=period_start,
            period_end=period_end,
            total_sources_used=0,
            generation_metadata={},
        )
        db.add(digest)
        await db.flush()
        return digest

    async def reset_for_regeneration(
        self,
        db: AsyncSession,
        digest: Digest,
        *,
        title: str,
    ) -> Digest:
        await db.execute(delete(DigestSection).where(DigestSection.digest_id == digest.id))
        digest.title = title
        digest.status = DigestStatus.GENERATING
        digest.summary = None
        digest.s3_archive_key = None
        digest.total_sources_used = 0
        digest.generation_metadata = {}
        digest.error_message = None
        digest.completed_at = None
        await db.flush()
        return digest

    async def mark_ready(
        self,
        db: AsyncSession,
        digest: Digest,
        *,
        s3_archive_key: str,
        total_sources_used: int,
        generation_metadata: dict[str, Any],
        completed_at: datetime,
    ) -> Digest:
        digest.status = DigestStatus.READY
        digest.s3_archive_key = s3_archive_key
        digest.total_sources_used = total_sources_used
        digest.generation_metadata = generation_metadata
        digest.error_message = None
        digest.completed_at = completed_at
        await db.flush()
        return digest

    async def mark_failed(
        self,
        db: AsyncSession,
        digest: Digest,
        *,
        error_message: str,
        completed_at: datetime,
        generation_metadata: dict[str, Any] | None = None,
    ) -> Digest:
        digest.status = DigestStatus.FAILED
        digest.error_message = error_message
        digest.completed_at = completed_at
        if generation_metadata is not None:
            digest.generation_metadata = generation_metadata
        await db.flush()
        return digest

    async def add_sections(
        self,
        db: AsyncSession,
        digest_id: uuid.UUID,
        sections: list[DigestSection],
    ) -> list[DigestSection]:
        for section in sections:
            db.add(section)
        await db.flush()
        return sections


digest_repository = DigestRepository()
