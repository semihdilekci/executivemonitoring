"""Digest listeleme, detay, manuel üretim ve anlık etki iş mantığı (Faz 6.5).

ADR-0003: üretim `newsletter_templates` kaydı (`newsletter_template_id`) ile
tetiklenir; 3-aşamalı editör pipeline (`DigestGenerator`) koşar. Anlık
"Yıldız'ı nasıl etkiler?" (`news-impact`) tek `processed_item` + global
`system_settings` prompt'larıyla runtime LLM çağrısıdır; **kalıcılaştırılmaz**.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from typing import Any

from packages.shared.enums import DigestStatus, LlmRequestType, UserRole
from packages.shared.models.digest import Digest
from packages.shared.models.newsletter_template import NewsletterTemplate
from packages.shared.models.user import User
from services.ai_engine.digest_generator import DigestGenerator, build_digest_title
from services.ai_engine.digest_repository import DigestRepository, digest_repository
from services.ai_engine.editor_selector import render_prompt
from services.ai_engine.exceptions import AIEngineHTTPError
from services.ai_engine.llm_client import LLMClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.exceptions import (
    AiProvidersUnavailableException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from apps.api.repositories.newsletter_template_repository import (
    NewsletterTemplateRepository,
    newsletter_template_repository,
)
from apps.api.repositories.processed_item_repository import (
    ProcessedItemRepository,
    SourceReferenceMetadata,
)
from apps.api.repositories.settings_repository import SettingsRepository
from apps.api.schemas.common import PaginationMeta
from apps.api.schemas.digest import (
    DigestDetailResponse,
    DigestListItemResponse,
    DigestListResponse,
    DigestSectionResponse,
    GenerateDigestRequest,
    GenerateDigestResponse,
    NewsImpactResponse,
    SourceReferenceResponse,
)
from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService
from apps.api.services.audit_service import AuditService, audit_service
from apps.api.services.llm_client_factory import build_llm_client
from apps.api.services.notification_service import notification_service

logger = logging.getLogger("ygip.api.digest_service")

_DIGEST_DEFAULT_LIMIT = 10
_DIGEST_MAX_LIMIT = 50

_IMPACT_SYSTEM_KEY = "newsletter_impact_system_prompt"
_IMPACT_USER_KEY = "newsletter_impact_user_prompt"
_DEFAULT_IMPACT_SYSTEM_PROMPT = (
    "Sen YıldızHolding üst yönetimine danışmanlık yapan kıdemli bir strateji "
    "analistisin. Tek bir haberin YıldızHolding üzerindeki olası etkisini "
    "değerlendirirsin. SADECE düz metin yaz; markdown, başlık, tablo, madde "
    "işareti, kalın yazı veya emoji KULLANMA. Yanıtın Türkçe, somut, ağdasız "
    "ve en fazla 3-4 cümle olmalıdır."
)
_DEFAULT_IMPACT_USER_PROMPT = (
    "Haber başlığı: {title}\n\nHaber içeriği:\n{content}\n\n"
    "Bu gelişmenin etkisini şu yapıda, kısa ve somut değerlendir: "
    "(1) etkilenen YıldızHolding iş kolu veya markası, "
    "(2) kurumsal/M&A açısından fırsat veya risk, (3) önerilen aksiyon. "
    "En fazla 3-4 cümle, düz metin, ağdasız bir dille."
)

GenerationScheduler = Callable[..., Awaitable[None]]
LLMClientFactory = Callable[..., Awaitable[LLMClient]]


def _to_list_item(digest: Digest) -> DigestListItemResponse:
    return DigestListItemResponse.model_validate(digest)


def _collect_reference_ids(digest: Digest) -> list[uuid.UUID]:
    """Bölüm `source_references` JSONB içindeki tüm processed_item id'lerini toplar."""
    ids: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for section in digest.sections:
        if not isinstance(section.source_references, list):
            continue
        for item in section.source_references:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("processed_item_id")
            if not raw_id:
                continue
            try:
                item_id = uuid.UUID(str(raw_id))
            except ValueError:
                continue
            if item_id not in seen:
                seen.add(item_id)
                ids.append(item_id)
    return ids


def _to_section_response(
    section: Any,
    metadata: dict[uuid.UUID, SourceReferenceMetadata] | None = None,
) -> DigestSectionResponse:
    metadata = metadata or {}
    refs = []
    for item in section.source_references:
        if not isinstance(item, dict) or not item.get("processed_item_id") or not item.get("title"):
            continue
        item_id = uuid.UUID(str(item["processed_item_id"]))
        meta = metadata.get(item_id)
        refs.append(
            SourceReferenceResponse(
                processed_item_id=item_id,
                title=str(item.get("title", "")),
                url=item.get("url"),
                summary=item.get("summary"),
                source_name=meta.source_name if meta else None,
                published_at=meta.published_at if meta else None,
            )
        )
    return DigestSectionResponse(
        id=section.id,
        section_order=section.section_order,
        section_title=section.section_title,
        ai_summary=section.ai_summary,
        impact_note=section.impact_note,
        source_references=refs,
    )


def _to_detail_response(
    digest: Digest,
    metadata: dict[uuid.UUID, SourceReferenceMetadata] | None = None,
) -> DigestDetailResponse:
    sections = sorted(digest.sections, key=lambda item: item.section_order)
    return DigestDetailResponse(
        **_to_list_item(digest).model_dump(),
        summary=digest.summary,
        sections=[_to_section_response(section, metadata) for section in sections],
    )


class DigestService:
    """Digest okuma, asenkron üretim tetikleme ve anlık etki analizi."""

    def __init__(
        self,
        digests: DigestRepository | None = None,
        audit_svc: AuditService | None = None,
        llm_client_factory: LLMClientFactory | None = None,
        generation_scheduler: GenerationScheduler | None = None,
        newsletter_templates: NewsletterTemplateRepository | None = None,
        processed_items: ProcessedItemRepository | None = None,
        settings_repo: SettingsRepository | None = None,
    ) -> None:
        self._digests = digests or digest_repository
        self._audit_service = audit_svc or audit_service
        self._llm_client_factory = llm_client_factory
        self._generation_scheduler = generation_scheduler
        self._newsletter_templates = newsletter_templates or newsletter_template_repository
        self._processed_items = processed_items or ProcessedItemRepository()
        self._settings_repo = settings_repo or SettingsRepository()

    async def list_digests(
        self,
        db: AsyncSession,
        *,
        user: User,
        cursor: str | None = None,
        limit: int = _DIGEST_DEFAULT_LIMIT,
        newsletter_slug: str | None = None,
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
            newsletter_slug=newsletter_slug,
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
        ref_ids = _collect_reference_ids(digest)
        metadata = await self._processed_items.get_source_metadata_by_ids(db, ref_ids)
        return _to_detail_response(digest, metadata)

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
        newsletter = await self._newsletter_templates.get_by_id(
            db, body.newsletter_template_id
        )
        if newsletter is None:
            raise NotFoundException(message="Bülten şablonu bulunamadı.")

        period_start, period_end = self._resolve_period(
            newsletter,
            period_start=body.period_start,
            period_end=body.period_end,
        )

        title = build_digest_title(newsletter.name, period_start, period_end)
        existing = await self._digests.find_for_period(
            db,
            newsletter_slug=newsletter.slug,
            period_start=period_start,
            period_end=period_end,
        )
        if existing is None:
            digest = await self._digests.create_generating(
                db,
                newsletter_slug=newsletter.slug,
                newsletter_template_id=newsletter.id,
                title=title,
                period_start=period_start,
                period_end=period_end,
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
                "newsletter_slug": newsletter.slug,
                "newsletter_template_id": str(newsletter.id),
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "trigger": "manual",
            },
        )

        scheduler = self._generation_scheduler or self._default_generation_scheduler
        await scheduler(
            session_factory=session_factory,
            newsletter_template_id=newsletter.id,
            period_start=period_start,
            period_end=period_end,
            actor_user_id=actor.id,
            api_key_service=api_key_service,
            api_usage_service=api_usage_service,
        )

        return GenerateDigestResponse(
            id=digest.id,
            status=DigestStatus.GENERATING,
        )

    async def news_impact(
        self,
        db: AsyncSession,
        *,
        processed_item_id: uuid.UUID,
        api_key_service: ApiKeyService,
        api_usage_service: ApiUsageService,
    ) -> NewsImpactResponse:
        """Tek haber için anlık Yıldız etki analizi — global prompt, kalıcı değil."""
        row = await self._processed_items.get_by_id(db, "news", processed_item_id)
        if row is None:
            raise NotFoundException(
                message="Haber bulunamadı.",
                error_code="PROCESSED_ITEM_NOT_FOUND",
            )

        system_prompt, user_prompt_template = await self._impact_prompts(db)
        context = {
            "title": row.title,
            "article_title": row.title,
            "content": row.clean_content,
            "article_content": row.clean_content,
            "source": row.source_name,
        }
        user_prompt = render_prompt(user_prompt_template, context)
        rendered_system = render_prompt(system_prompt, context)

        try:
            llm_client = await self._resolve_llm_client(
                db, api_key_service, api_usage_service
            )
            response = await llm_client.complete(
                user_prompt,
                system_prompt=rendered_system,
                max_tokens=512,
                operation_type=LlmRequestType.CHATBOT,
            )
        except AIEngineHTTPError as exc:
            logger.warning(
                "news_impact_llm_unavailable",
                extra={"processed_item_id": str(processed_item_id), "error": str(exc)},
            )
            raise AiProvidersUnavailableException() from exc

        return NewsImpactResponse(analysis=response.text.strip())

    async def _impact_prompts(self, db: AsyncSession) -> tuple[str, str]:
        system_setting = await self._settings_repo.get_by_key(db, _IMPACT_SYSTEM_KEY)
        user_setting = await self._settings_repo.get_by_key(db, _IMPACT_USER_KEY)
        system_prompt = (
            str(system_setting.value)
            if system_setting is not None and isinstance(system_setting.value, str)
            else _DEFAULT_IMPACT_SYSTEM_PROMPT
        )
        user_prompt = (
            str(user_setting.value)
            if user_setting is not None and isinstance(user_setting.value, str)
            else _DEFAULT_IMPACT_USER_PROMPT
        )
        return system_prompt, user_prompt

    async def _resolve_llm_client(
        self,
        db: AsyncSession,
        api_key_service: ApiKeyService,
        api_usage_service: ApiUsageService,
    ) -> LLMClient:
        if self._llm_client_factory is not None:
            return await self._llm_client_factory(db)
        return await build_llm_client(db, api_key_service, api_usage_service)

    @staticmethod
    def _resolve_period(
        newsletter: NewsletterTemplate,
        *,
        period_start: date | None,
        period_end: date | None,
    ) -> tuple[date, date]:
        if period_start is not None and period_end is not None:
            if period_end < period_start:
                raise ValidationException(
                    message="Dönem bitiş tarihi başlangıçtan önce olamaz."
                )
            return period_start, period_end
        if period_start is not None or period_end is not None:
            raise ValidationException(
                message="period_start ve period_end birlikte verilmelidir."
            )
        end = date.today()
        start = end - timedelta(days=max(1, newsletter.date_range_days))
        return start, end

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
        newsletter_template_id: uuid.UUID,
        period_start: date,
        period_end: date,
        actor_user_id: uuid.UUID,
        api_key_service: ApiKeyService,
        api_usage_service: ApiUsageService,
    ) -> None:
        asyncio.create_task(
            _run_digest_generation(
                session_factory=session_factory,
                newsletter_template_id=newsletter_template_id,
                period_start=period_start,
                period_end=period_end,
                actor_user_id=actor_user_id,
                api_key_service=api_key_service,
                api_usage_service=api_usage_service,
                llm_client_factory=self._llm_client_factory,
                audit_service=self._audit_service,
                newsletter_templates=self._newsletter_templates,
            )
        )


async def _run_digest_generation(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    newsletter_template_id: uuid.UUID,
    period_start: date,
    period_end: date,
    actor_user_id: uuid.UUID,
    api_key_service: ApiKeyService,
    api_usage_service: ApiUsageService,
    llm_client_factory: LLMClientFactory | None,
    audit_service: AuditService,
    newsletter_templates: NewsletterTemplateRepository,
) -> None:
    async with session_factory() as db:
        try:
            newsletter = await newsletter_templates.get_by_id(db, newsletter_template_id)
            if newsletter is None:
                logger.error(
                    "digest_background_newsletter_missing",
                    extra={"newsletter_template_id": str(newsletter_template_id)},
                )
                return

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
                audit_hook=audit_hook,
                notification_hook=notification_hook,
            )
            await generator.generate(
                db,
                newsletter=newsletter,
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
                    "newsletter_template_id": str(newsletter_template_id),
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                },
            )


digest_service = DigestService()
