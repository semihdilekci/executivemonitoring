"""Digest listeleme, detay ve manuel üretim iş mantığı."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from packages.shared.enums import DigestStatus, DigestType, UserRole
from packages.shared.models.digest import Digest
from packages.shared.models.user import User
from services.ai_engine.digest_generator import DigestGenerator, build_digest_title
from services.ai_engine.digest_repository import DigestRepository, digest_repository
from services.ai_engine.llm_client import LLMClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from apps.api.schemas.common import PaginationMeta
from apps.api.schemas.digest import (
    DigestDetailResponse,
    DigestListItemResponse,
    DigestListResponse,
    DigestSectionResponse,
    GenerateDigestRequest,
    GenerateDigestResponse,
    SourceReferenceResponse,
)
from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService
from apps.api.services.audit_service import AuditService, audit_service
from apps.api.services.llm_client_factory import build_llm_client
from apps.api.services.notification_service import notification_service
from apps.api.services.prompt_template_resolver import db_prompt_template_resolver

logger = logging.getLogger("ygip.api.digest_service")

_DIGEST_DEFAULT_LIMIT = 10
_DIGEST_MAX_LIMIT = 50

GenerationScheduler = Callable[..., Awaitable[None]]


def _to_list_item(digest: Digest) -> DigestListItemResponse:
    return DigestListItemResponse.model_validate(digest)


def _to_section_response(section: Any) -> DigestSectionResponse:
    refs = [
        SourceReferenceResponse(
            processed_item_id=uuid.UUID(str(item["processed_item_id"])),
            title=str(item.get("title", "")),
            url=item.get("url"),
        )
        for item in section.source_references
        if isinstance(item, dict) and item.get("processed_item_id") and item.get("title")
    ]
    return DigestSectionResponse(
        id=section.id,
        section_order=section.section_order,
        section_title=section.section_title,
        ai_summary=section.ai_summary,
        impact_note=section.impact_note,
        source_references=refs,
    )


def _to_detail_response(digest: Digest) -> DigestDetailResponse:
    sections = sorted(digest.sections, key=lambda item: item.section_order)
    return DigestDetailResponse(
        **_to_list_item(digest).model_dump(),
        sections=[_to_section_response(section) for section in sections],
    )


class DigestService:
    """Digest okuma ve asenkron üretim tetikleme."""

    def __init__(
        self,
        digests: DigestRepository | None = None,
        audit_svc: AuditService | None = None,
        llm_client_factory: Callable[..., Awaitable[LLMClient]] | None = None,
        generation_scheduler: GenerationScheduler | None = None,
    ) -> None:
        self._digests = digests or digest_repository
        self._audit_service = audit_svc or audit_service
        self._llm_client_factory = llm_client_factory
        self._generation_scheduler = generation_scheduler

    async def list_digests(
        self,
        db: AsyncSession,
        *,
        user: User,
        cursor: str | None = None,
        limit: int = _DIGEST_DEFAULT_LIMIT,
        digest_type: DigestType | None = None,
        status: DigestStatus | None = None,
    ) -> DigestListResponse:
        resolved_limit = min(max(limit, 1), _DIGEST_MAX_LIMIT)
        resolved_status = self._resolve_list_status(user, status)

        cursor_id: uuid.UUID | None = None
        if cursor is not None:
            try:
                cursor_id = uuid.UUID(cursor)
            except ValueError as exc:
                raise NotFoundException(message="Geçersiz pagination cursor.") from exc

        digests, next_cursor, has_more = await self._digests.list_paginated(
            db,
            cursor=cursor_id,
            limit=resolved_limit,
            digest_type=digest_type,
            status=resolved_status,
        )
        return DigestListResponse(
            data=[_to_list_item(item) for item in digests],
            pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more),
        )

    async def get_digest(
        self,
        db: AsyncSession,
        *,
        user: User,
        digest_id: uuid.UUID,
    ) -> DigestDetailResponse:
        digest = await self._digests.get_by_id(db, digest_id)
        if digest is None or self._is_hidden_from_user(digest, user):
            raise NotFoundException(message="Bülten bulunamadı.")
        return _to_detail_response(digest)

    async def initiate_generation(
        self,
        db: AsyncSession,
        *,
        actor: User,
        body: GenerateDigestRequest,
        session_factory: async_sessionmaker[AsyncSession],
        api_key_service: ApiKeyService,
        api_usage_service: ApiUsageService,
    ) -> GenerateDigestResponse:
        if body.period_end < body.period_start:
            raise ValidationException(message="Dönem bitiş tarihi başlangıçtan önce olamaz.")

        title = build_digest_title(body.digest_type, body.period_start, body.period_end)
        existing = await self._digests.find_for_period(
            db,
            digest_type=body.digest_type,
            period_start=body.period_start,
            period_end=body.period_end,
        )
        if existing is None:
            digest = await self._digests.create_generating(
                db,
                digest_type=body.digest_type,
                title=title,
                period_start=body.period_start,
                period_end=body.period_end,
            )
        else:
            digest = await self._digests.reset_for_regeneration(db, existing, title=title)

        await self._audit_service.log_event(
            db,
            event_type="digest.started",
            actor_user_id=actor.id,
            target_type="digest",
            target_id=digest.id,
            payload={
                "digest_type": body.digest_type.value,
                "period_start": body.period_start.isoformat(),
                "period_end": body.period_end.isoformat(),
                "trigger": "manual",
            },
        )

        scheduler = self._generation_scheduler or self._default_generation_scheduler
        await scheduler(
            session_factory=session_factory,
            digest_type=body.digest_type,
            period_start=body.period_start,
            period_end=body.period_end,
            actor_user_id=actor.id,
            api_key_service=api_key_service,
            api_usage_service=api_usage_service,
        )

        return GenerateDigestResponse(
            id=digest.id,
            status=DigestStatus.GENERATING,
        )

    def _resolve_list_status(
        self,
        user: User,
        status: DigestStatus | None,
    ) -> DigestStatus | None:
        if user.role == UserRole.VIEWER:
            if status is not None and status != DigestStatus.READY:
                raise ForbiddenException(
                    message="Yalnızca yayınlanmış bültenleri görüntüleyebilirsiniz.",
                )
            return DigestStatus.READY
        return status or DigestStatus.READY

    def _is_hidden_from_user(self, digest: Digest, user: User) -> bool:
        return user.role == UserRole.VIEWER and digest.status != DigestStatus.READY

    async def _default_generation_scheduler(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        digest_type: DigestType,
        period_start: date,
        period_end: date,
        actor_user_id: uuid.UUID,
        api_key_service: ApiKeyService,
        api_usage_service: ApiUsageService,
    ) -> None:
        asyncio.create_task(
            _run_digest_generation(
                session_factory=session_factory,
                digest_type=digest_type,
                period_start=period_start,
                period_end=period_end,
                actor_user_id=actor_user_id,
                api_key_service=api_key_service,
                api_usage_service=api_usage_service,
                llm_client_factory=self._llm_client_factory,
                audit_service=self._audit_service,
            )
        )


async def _run_digest_generation(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    digest_type: DigestType,
    period_start: date,
    period_end: date,
    actor_user_id: uuid.UUID,
    api_key_service: ApiKeyService,
    api_usage_service: ApiUsageService,
    llm_client_factory: Callable[..., Awaitable[LLMClient]] | None,
    audit_service: AuditService,
) -> None:
    async with session_factory() as db:
        try:
            if llm_client_factory is not None:
                llm_client = await llm_client_factory(db)
            else:
                llm_client = await build_llm_client(db, api_key_service, api_usage_service)

            async def audit_hook(
                session: AsyncSession,
                *,
                event_type: str,
                actor_user_id: uuid.UUID | None,
                target_type: str | None,
                target_id: uuid.UUID,
                payload: dict[str, Any],
            ) -> None:
                if event_type == "digest.started":
                    return
                await audit_service.log_event(
                    session,
                    event_type=event_type,
                    actor_user_id=actor_user_id,
                    target_type=target_type,
                    target_id=target_id,
                    payload=payload,
                )

            async def notification_hook(
                session: AsyncSession,
                digest: Digest,
                success: bool,
                _error_message: str | None,
            ) -> None:
                if not success:
                    return
                await notification_service.send_digest_ready(session, digest=digest)

            generator = DigestGenerator(
                llm_client=llm_client,
                template_resolver=db_prompt_template_resolver,
                audit_hook=audit_hook,
                notification_hook=notification_hook,
            )
            await generator.generate(
                db,
                digest_type=digest_type,
                period_start=period_start,
                period_end=period_end,
                actor_user_id=actor_user_id,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception(
                "digest_background_generation_failed",
                extra={
                    "digest_type": digest_type.value,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                },
            )


digest_service = DigestService()
