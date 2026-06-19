"""Digest üretim orchestrator — makale seçimi → prompt → LLM → parse → persist."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime
from typing import Any, Protocol

from packages.shared.enums import DigestType, LlmRequestType
from packages.shared.models.digest import Digest
from packages.shared.models.digest_section import DigestSection
from packages.shared.models.prompt_template import PromptTemplate
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_engine.archive_service import DigestArchiveService, digest_archive_service
from services.ai_engine.digest_models import (
    DIGEST_TYPE_QUERY_CONFIG,
    DIGEST_TYPE_TITLES,
    SECTION_ORDER,
    DigestArticle,
    ParsedDigestSection,
)
from services.ai_engine.digest_parser import parse_llm_sections
from services.ai_engine.digest_repository import DigestRepository, digest_repository
from services.ai_engine.exceptions import (
    DigestGenerationError,
    DigestParseError,
    NoArticlesForDigestError,
    NoPromptTemplatesError,
)
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.processed_item_repository import (
    ProcessedItemRepository,
    processed_item_repository,
)
from services.ai_engine.prompt_renderer import PromptRenderer

logger = logging.getLogger("ygip.ai_engine.digest_generator")

AuditHook = Callable[..., Awaitable[None]]
NotificationHook = Callable[[AsyncSession, Digest, bool, str | None], Awaitable[None]]


class PromptTemplateResolver(Protocol):
    """Aktif prompt şablonu çözümleme arayüzü."""

    async def list_active_templates(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType,
    ) -> list[PromptTemplate]: ...


async def _noop_notification(
    _db: AsyncSession,
    _digest: Digest,
    success: bool,
    error_message: str | None,
) -> None:
    logger.info(
        "digest_notification_stub",
        extra={
            "digest_id": str(_digest.id),
            "success": success,
            "error_message": error_message,
        },
    )


class DigestGenerator:
    """3 digest_type için bülten üretimi."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_renderer: PromptRenderer | None = None,
        processed_items: ProcessedItemRepository | None = None,
        digests: DigestRepository | None = None,
        archive_service: DigestArchiveService | None = None,
        template_resolver: PromptTemplateResolver | None = None,
        audit_hook: AuditHook | None = None,
        notification_hook: NotificationHook | None = None,
        article_limit: int = 50,
        min_relevance_score: float = 0.0,
    ) -> None:
        self._llm_client = llm_client
        self._prompt_renderer = prompt_renderer or PromptRenderer()
        self._processed_items = processed_items or processed_item_repository
        self._digests = digests or digest_repository
        self._archive_service = archive_service or digest_archive_service
        self._template_resolver = template_resolver
        self._audit_hook = audit_hook
        self._notification_hook = notification_hook or _noop_notification
        self._article_limit = article_limit
        self._min_relevance_score = min_relevance_score

    async def generate(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType,
        period_start: date,
        period_end: date,
        actor_user_id: uuid.UUID | None = None,
    ) -> Digest:
        """Digest üretir — başarıda `ready`, hatada `failed`."""
        title = build_digest_title(digest_type, period_start, period_end)
        digest = await self._get_or_create_digest(
            db,
            digest_type=digest_type,
            title=title,
            period_start=period_start,
            period_end=period_end,
        )

        await self._audit(
            db,
            event_type="digest.started",
            actor_user_id=actor_user_id,
            target_id=digest.id,
            payload={
                "digest_type": digest_type.value,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )

        metadata: dict[str, Any] = {
            "digest_type": digest_type.value,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }

        try:
            articles = await self._select_articles(
                db,
                digest_type=digest_type,
                period_start=period_start,
                period_end=period_end,
            )
            if not articles:
                raise NoArticlesForDigestError()

            templates = await self._load_templates(db, digest_type=digest_type)
            if not templates:
                raise NoPromptTemplatesError()

            parsed_sections = await self._generate_sections(
                articles=articles,
                templates=templates,
                digest_type=digest_type,
                period_start=period_start,
                period_end=period_end,
            )

            digest_sections = self._build_digest_sections(
                digest_id=digest.id,
                parsed_sections=parsed_sections,
                templates=templates,
            )
            await self._digests.add_sections(db, digest.id, digest_sections)

            archive_key = await self._archive_service.upload_html(
                digest=digest,
                sections=digest_sections,
            )

            metadata.update(
                {
                    "article_count": len(articles),
                    "section_count": len(digest_sections),
                    "providers_used": list(
                        {
                            section.prompt_template_id
                            for section in digest_sections
                            if section.prompt_template_id is not None
                        }
                    ),
                }
            )

            completed_at = datetime.now(UTC)
            await self._digests.mark_ready(
                db,
                digest,
                s3_archive_key=archive_key,
                total_sources_used=len(articles),
                generation_metadata=metadata,
                completed_at=completed_at,
            )

            await self._audit(
                db,
                event_type="digest.completed",
                actor_user_id=actor_user_id,
                target_id=digest.id,
                payload={
                    "digest_type": digest_type.value,
                    "article_count": len(articles),
                    "section_count": len(digest_sections),
                },
            )
            await self._notification_hook(
                db,
                digest,
                True,
                None,
            )
            return digest

        except DigestGenerationError as exc:
            await self._handle_failure(
                db,
                digest=digest,
                actor_user_id=actor_user_id,
                error_message=str(exc),
                metadata=metadata,
            )
            raise
        except Exception as exc:
            logger.exception(
                "digest_generation_unexpected_error",
                extra={"digest_id": str(digest.id), "digest_type": digest_type.value},
            )
            await self._handle_failure(
                db,
                digest=digest,
                actor_user_id=actor_user_id,
                error_message="Bülten üretimi sırasında beklenmeyen hata oluştu.",
                metadata=metadata,
            )
            raise DigestGenerationError(
                "Bülten üretimi sırasında beklenmeyen hata oluştu.",
            ) from exc

    async def _get_or_create_digest(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType,
        title: str,
        period_start: date,
        period_end: date,
    ) -> Digest:
        existing = await self._digests.find_for_period(
            db,
            digest_type=digest_type,
            period_start=period_start,
            period_end=period_end,
        )
        if existing is not None:
            return await self._digests.reset_for_regeneration(db, existing, title=title)
        return await self._digests.create_generating(
            db,
            digest_type=digest_type,
            title=title,
            period_start=period_start,
            period_end=period_end,
        )

    async def _select_articles(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType,
        period_start: date,
        period_end: date,
    ) -> list[DigestArticle]:
        config = DIGEST_TYPE_QUERY_CONFIG[digest_type.value]
        return await self._processed_items.list_for_digest(
            db,
            config=config,
            period_start=period_start,
            period_end=period_end,
            min_relevance_score=self._min_relevance_score,
            limit=self._article_limit,
        )

    async def _load_templates(
        self,
        db: AsyncSession,
        *,
        digest_type: DigestType,
    ) -> list[PromptTemplate]:
        if self._template_resolver is None:
            raise NoPromptTemplatesError()
        templates = await self._template_resolver.list_active_templates(
            db,
            digest_type=digest_type,
        )
        order = SECTION_ORDER.get(digest_type.value, [])
        if not order:
            return sorted(templates, key=lambda item: item.section_key)
        order_index = {key: index for index, key in enumerate(order)}
        return sorted(
            templates,
            key=lambda item: (order_index.get(item.section_key, len(order)), item.section_key),
        )

    async def _generate_sections(
        self,
        *,
        articles: list[DigestArticle],
        templates: list[PromptTemplate],
        digest_type: DigestType,
        period_start: date,
        period_end: date,
    ) -> list[ParsedDigestSection]:
        articles_text = format_articles_for_prompt(articles)
        date_range = f"{period_start.isoformat()} — {period_end.isoformat()}"
        parsed_sections: list[ParsedDigestSection] = []

        for template in templates:
            context = {
                "articles": articles_text,
                "context": articles_text,
                "date_range": date_range,
                "digest_type": digest_type.value,
            }
            user_prompt = self._prompt_renderer.render_user_prompt(
                template.user_prompt_template,
                context=context,
            )
            response = await self._llm_client.complete(
                user_prompt,
                system_prompt=template.system_prompt,
                operation_type=LlmRequestType.DIGEST_GENERATION,
            )

            try:
                sections = parse_llm_sections(
                    response.text,
                    section_key=template.section_key,
                    articles=articles,
                )
            except DigestParseError as exc:
                raise DigestParseError(
                    f"{template.section_key} bölümü parse edilemedi: {exc}",
                ) from exc

            if not sections:
                raise DigestParseError(f"{template.section_key} bölümü boş döndü.")

            section = sections[0]
            parsed_sections.append(
                ParsedDigestSection(
                    section_title=section.section_title,
                    ai_summary=section.ai_summary,
                    impact_note=section.impact_note,
                    source_references=section.source_references,
                    section_key=template.section_key,
                    prompt_template_id=template.id,
                )
            )

        return parsed_sections

    def _build_digest_sections(
        self,
        *,
        digest_id: uuid.UUID,
        parsed_sections: list[ParsedDigestSection],
        templates: list[PromptTemplate],
    ) -> list[DigestSection]:
        template_by_key = {template.section_key: template for template in templates}
        sections: list[DigestSection] = []
        for index, parsed in enumerate(parsed_sections, start=1):
            section_key = parsed.section_key or f"section_{index}"
            template = template_by_key.get(section_key)
            prompt_template_id = parsed.prompt_template_id
            if prompt_template_id is None and template is not None:
                prompt_template_id = template.id
            sections.append(
                DigestSection(
                    digest_id=digest_id,
                    section_order=index,
                    section_title=parsed.section_title,
                    ai_summary=parsed.ai_summary,
                    impact_note=parsed.impact_note,
                    source_references=[ref.to_json() for ref in parsed.source_references],
                    prompt_template_id=prompt_template_id,
                )
            )
        return sections

    async def _handle_failure(
        self,
        db: AsyncSession,
        *,
        digest: Digest,
        actor_user_id: uuid.UUID | None,
        error_message: str,
        metadata: dict[str, Any],
    ) -> None:
        completed_at = datetime.now(UTC)
        metadata["error_message"] = error_message
        await self._digests.mark_failed(
            db,
            digest,
            error_message=error_message,
            completed_at=completed_at,
            generation_metadata=metadata,
        )
        await self._audit(
            db,
            event_type="digest.failed",
            actor_user_id=actor_user_id,
            target_id=digest.id,
            payload={
                "digest_type": digest.digest_type.value,
                "error_message": error_message,
            },
        )
        await self._notification_hook(
            db,
            digest,
            False,
            error_message,
        )

    async def _audit(
        self,
        db: AsyncSession,
        *,
        event_type: str,
        actor_user_id: uuid.UUID | None,
        target_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> None:
        if self._audit_hook is None:
            return
        await self._audit_hook(
            db,
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_type="digest",
            target_id=target_id,
            payload=payload,
        )


_TURKISH_MONTHS = (
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)


def build_digest_title(digest_type: DigestType, period_start: date, period_end: date) -> str:
    """Bülten başlığı — Türkçe tarih aralığı."""
    base = DIGEST_TYPE_TITLES.get(digest_type.value, "Haftalık Bülten")
    if period_start.year == period_end.year and period_start.month == period_end.month:
        month = _TURKISH_MONTHS[period_start.month - 1]
        return f"{base} — {period_start.day}-{period_end.day} {month} {period_start.year}"
    return f"{base} — {period_start.isoformat()} / {period_end.isoformat()}"


def format_articles_for_prompt(articles: list[DigestArticle], *, max_chars: int = 12000) -> str:
    """Makale listesini prompt context metnine dönüştürür."""
    if not articles:
        return ""

    blocks: list[str] = []
    used = 0
    for index, article in enumerate(articles, start=1):
        header = f"### Makale {index}: {article.title}"
        meta_lines = [f"ID: {article.processed_item_id}", f"Skor: {article.relevance_score:.2f}"]
        if article.url:
            meta_lines.append(f"URL: {article.url}")
        if article.published_at is not None:
            meta_lines.append(f"Tarih: {article.published_at.date().isoformat()}")
        body = article.clean_content.strip()
        block = "\n".join([header, *meta_lines, body, ""])
        if used + len(block) > max_chars and blocks:
            break
        blocks.append(block)
        used += len(block)
    return "\n".join(blocks).strip()
