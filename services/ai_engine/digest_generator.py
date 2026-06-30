"""Digest üretim orchestrator — 3-aşamalı editör pipeline (Faz 6.5, ADR-0003).

`Docs/04` §9.2:
- **Aşama 0–1 (editör):** aday havuz + dağıtım + haftalık özet (`editor_selector`).
- **Aşama 2 (bölüm):** editörün atadığı haberlerden bölüm özeti + Yıldız etki
  notu (`section_generator`).
- **Aşama 3 (kayıt):** `digests` (`summary`, `newsletter_slug`,
  `newsletter_template_id`, `total_sources_used`) + tüm `digest_sections` tek
  transaction'da; status `ready`. Herhangi bölüm parse hatası → digest `failed`.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, date, datetime
from typing import Any, Protocol

from packages.shared.models.digest import Digest
from packages.shared.models.digest_section import DigestSection
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_engine.archive_service import DigestArchiveService, digest_archive_service
from services.ai_engine.digest_models import DigestArticle, ParsedDigestSection
from services.ai_engine.digest_repository import DigestRepository, digest_repository
from services.ai_engine.editor_selector import EditorSelector
from services.ai_engine.exceptions import (
    DigestGenerationError,
    NoArticlesForDigestError,
)
from services.ai_engine.llm_client import LLMClient
from services.ai_engine.section_generator import GeneratableSection, SectionGenerator

logger = logging.getLogger("ygip.ai_engine.digest_generator")


class GeneratableNewsletter(Protocol):
    """Pipeline'ın bültenden ihtiyaç duyduğu minimum arayüz.

    `NewsletterTemplate` ORM bunu yapısal olarak karşılar; `editor_selector`'ın
    `NewsletterLike`'ı bu protokolün alt kümesidir.
    """

    id: uuid.UUID
    slug: str
    name: str
    description: str
    summary_system_prompt: str
    summary_user_prompt: str
    min_content_score: int

    # Salt-okunur property: ORM `Mapped[list[str]]` invariant bir attribute olarak
    # `Sequence[str]`'i karşılamaz; property kovaryant olduğundan `list[str]` uyar.
    @property
    def content_categories(self) -> Sequence[str]: ...

    @property
    def sections(self) -> Sequence[GeneratableSection]: ...

AuditHook = Callable[..., Awaitable[None]]
NotificationHook = Callable[[AsyncSession, Digest, bool, str | None], Awaitable[None]]


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
    """Serbest bülten üretimi — editör → bölüm pipeline orchestrate (Faz 6.5)."""

    def __init__(
        self,
        *,
        llm_client: LLMClient,
        editor_selector: EditorSelector | None = None,
        section_generator: SectionGenerator | None = None,
        digests: DigestRepository | None = None,
        archive_service: DigestArchiveService | None = None,
        audit_hook: AuditHook | None = None,
        notification_hook: NotificationHook | None = None,
    ) -> None:
        self._llm_client = llm_client
        self._editor = editor_selector or EditorSelector(llm_client=llm_client)
        self._sections = section_generator or SectionGenerator(llm_client=llm_client)
        self._digests = digests or digest_repository
        self._archive_service = archive_service or digest_archive_service
        self._audit_hook = audit_hook
        self._notification_hook = notification_hook or _noop_notification

    async def generate(
        self,
        db: AsyncSession,
        *,
        newsletter: GeneratableNewsletter,
        period_start: date,
        period_end: date,
        actor_user_id: uuid.UUID | None = None,
    ) -> Digest:
        """Bülten üretir — başarıda `ready`, hatada `failed`."""
        title = build_digest_title(newsletter.name, period_start, period_end)
        digest = await self._get_or_create_digest(
            db,
            newsletter=newsletter,
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
                "newsletter_slug": newsletter.slug,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )

        metadata: dict[str, Any] = {
            "newsletter_slug": newsletter.slug,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }

        try:
            candidates = await self._editor.select_candidates(
                db,
                newsletter=newsletter,
                period_start=period_start,
                period_end=period_end,
            )
            if not candidates:
                raise NoArticlesForDigestError()

            editor_result = await self._editor.run_editor(
                newsletter=newsletter,
                articles=candidates,
                period_start=period_start,
                period_end=period_end,
            )
            digest.summary = editor_result.summary or None

            articles_by_id = {article.processed_item_id: article for article in candidates}
            assigned_by_order = {
                assignment.sort_order: [
                    articles_by_id[article_id]
                    for article_id in assignment.article_ids
                    if article_id in articles_by_id
                ]
                for assignment in editor_result.assignments
            }

            distribution = _build_distribution(newsletter.sections, assigned_by_order)
            logger.info(
                "digest_distribution_summary",
                extra={
                    "candidate_count": len(candidates),
                    "dropped_count": len(editor_result.dropped),
                    "defined_section_count": len(newsletter.sections),
                    "assigned_section_count": sum(
                        1 for row in distribution if row["generated"]
                    ),
                },
            )
            for row in distribution:
                if not row["generated"]:
                    logger.warning(
                        "section_no_articles_assigned",
                        extra={"section": row["name"], "sort_order": row["sort_order"]},
                    )

            date_range = f"{period_start.isoformat()} — {period_end.isoformat()}"
            parsed_sections = await self._generate_sections(
                newsletter=newsletter,
                assigned_by_order=assigned_by_order,
                date_range=date_range,
            )

            digest_sections = self._build_digest_sections(
                digest_id=digest.id,
                parsed_sections=parsed_sections,
            )
            await self._digests.add_sections(db, digest.id, digest_sections)

            archive_key = await self._archive_service.upload_html(
                digest=digest,
                sections=digest_sections,
            )

            total_sources_used = _count_distinct_sources(parsed_sections)
            metadata.update(
                {
                    "candidate_count": len(candidates),
                    "section_count": len(digest_sections),
                    "defined_section_count": len(newsletter.sections),
                    "dropped_count": len(editor_result.dropped),
                    "total_sources_used": total_sources_used,
                    "distribution": distribution,
                }
            )

            completed_at = datetime.now(UTC)
            await self._digests.mark_ready(
                db,
                digest,
                s3_archive_key=archive_key,
                total_sources_used=total_sources_used,
                generation_metadata=metadata,
                completed_at=completed_at,
            )

            await self._audit(
                db,
                event_type="digest.completed",
                actor_user_id=actor_user_id,
                target_id=digest.id,
                payload={
                    "newsletter_slug": newsletter.slug,
                    "candidate_count": len(candidates),
                    "section_count": len(digest_sections),
                },
            )
            await self._notification_hook(db, digest, True, None)
            return digest

        except DigestGenerationError as exc:
            await self._handle_failure(
                db,
                digest=digest,
                newsletter_slug=newsletter.slug,
                actor_user_id=actor_user_id,
                error_message=str(exc),
                metadata=metadata,
            )
            raise
        except Exception as exc:
            logger.exception(
                "digest_generation_unexpected_error",
                extra={"digest_id": str(digest.id), "newsletter_slug": newsletter.slug},
            )
            await self._handle_failure(
                db,
                digest=digest,
                newsletter_slug=newsletter.slug,
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
        newsletter: GeneratableNewsletter,
        title: str,
        period_start: date,
        period_end: date,
    ) -> Digest:
        existing = await self._digests.find_for_period(
            db,
            newsletter_slug=newsletter.slug,
            period_start=period_start,
            period_end=period_end,
        )
        if existing is not None:
            return await self._digests.reset_for_regeneration(db, existing, title=title)
        return await self._digests.create_generating(
            db,
            newsletter_slug=newsletter.slug,
            newsletter_template_id=newsletter.id,
            title=title,
            period_start=period_start,
            period_end=period_end,
        )

    async def _generate_sections(
        self,
        *,
        newsletter: GeneratableNewsletter,
        assigned_by_order: dict[int, list[DigestArticle]],
        date_range: str,
    ) -> list[ParsedDigestSection]:
        """Her bölüm için atanan haberlerden özet üretir; boş atama atlanır."""
        parsed_sections: list[ParsedDigestSection] = []
        for section in sorted(newsletter.sections, key=lambda item: item.sort_order):
            articles = assigned_by_order.get(section.sort_order, [])
            if not articles:
                continue
            parsed = await self._sections.generate_section(
                section=section,
                newsletter_name=newsletter.name,
                articles=articles,
                date_range=date_range,
            )
            parsed_sections.append(parsed)
        return parsed_sections

    def _build_digest_sections(
        self,
        *,
        digest_id: uuid.UUID,
        parsed_sections: list[ParsedDigestSection],
    ) -> list[DigestSection]:
        sections: list[DigestSection] = []
        for index, parsed in enumerate(parsed_sections, start=1):
            sections.append(
                DigestSection(
                    digest_id=digest_id,
                    section_order=index,
                    section_title=parsed.section_title,
                    ai_summary=parsed.ai_summary,
                    impact_note=parsed.impact_note,
                    source_references=[ref.to_json() for ref in parsed.source_references],
                    newsletter_section_id=parsed.newsletter_section_id,
                )
            )
        return sections

    async def _handle_failure(
        self,
        db: AsyncSession,
        *,
        digest: Digest,
        newsletter_slug: str,
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
                "newsletter_slug": newsletter_slug,
                "error_message": error_message,
            },
        )
        await self._notification_hook(db, digest, False, error_message)

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


def build_digest_title(newsletter_name: str, period_start: date, period_end: date) -> str:
    """Bülten başlığı — bülten adı + Türkçe tarih aralığı."""
    if period_start.year == period_end.year and period_start.month == period_end.month:
        month = _TURKISH_MONTHS[period_start.month - 1]
        return (
            f"{newsletter_name} — "
            f"{period_start.day}-{period_end.day} {month} {period_start.year}"
        )
    return f"{newsletter_name} — {period_start.isoformat()} / {period_end.isoformat()}"


def _count_distinct_sources(parsed_sections: Sequence[ParsedDigestSection]) -> int:
    """Bölümlerde kullanılan benzersiz haber sayısı."""
    used: set[uuid.UUID] = set()
    for section in parsed_sections:
        for ref in section.source_references:
            used.add(ref.processed_item_id)
    return len(used)


def _build_distribution(
    sections: Sequence[GeneratableSection],
    assigned_by_order: dict[int, list[DigestArticle]],
) -> list[dict[str, Any]]:
    """Tanımlı her bölüm için editörün atadığı haber sayısı + üretilip üretilmediği.

    `_generate_sections` haber atanmamış bölümü atladığından (`generated=False`),
    bu liste "5 bölüm tanımlı ama 4'ü üretildi" durumunu ve sebebini (0 atama)
    pipeline detayında görünür kılar.
    """
    rows: list[dict[str, Any]] = []
    for section in sorted(sections, key=lambda item: item.sort_order):
        count = len(assigned_by_order.get(section.sort_order, []))
        rows.append(
            {
                "sort_order": section.sort_order,
                "name": section.name,
                "assigned_count": count,
                "generated": count > 0,
            }
        )
    return rows
