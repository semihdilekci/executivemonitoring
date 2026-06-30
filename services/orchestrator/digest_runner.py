"""Gerçek digest üretimini orkestratöre bağlayan runner (Faz 6.1 — İterasyon 5).

`DigestStageExecutor`'ın gerçek bağımlılığı: mevcut `DigestGenerator` akışını
(`Docs/04` §9) kendi DB session'ında koşturur — iş mantığı yeniden yazılmaz,
yalnızca çağrılır (`Docs/10` §6.1 Don'ts). Orkestratör kendi `session_factory`'sini
kullanır (background driver; request session'ına bağlı değil — `Docs/04` §10.5).

`DigestGenerator` LLM client + template resolver + audit/notification hook'larıyla
kurulur; bu kurulum `apps/api` katmanına özgü olduğundan (LLM key servisleri) buraya
`generator_factory` olarak enjekte edilir — böylece orkestratör paketi `apps/api`'ye
bağımlı kalmaz. `send_notification` hook gating'i factory'de yapılır (`Docs/06`
S-DIGEST-TRIGGER-CONFIRM: test modunda mail/push gitmez).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from packages.shared.enums import DigestStatus
from packages.shared.models.digest_section import DigestSection
from packages.shared.models.newsletter_template import NewsletterTemplate
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from services.ai_engine.digest_generator import DigestGenerator
from services.ai_engine.exceptions import DigestGenerationError
from services.orchestrator.stage_executors import DigestRequest, DigestRunResult

logger = logging.getLogger("ygip.orchestrator.digest")

# `digest.generation_metadata` içinden pipeline detayında gösterilecek alanlar.
_DIAGNOSTIC_KEYS = (
    "candidate_count",
    "dropped_count",
    "defined_section_count",
    "section_count",
    "total_sources_used",
    "distribution",
)


def _diagnostics_from_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    """`generation_metadata`'dan dağıtım diagnostiğini ayıklar (yoksa `None`)."""
    if not metadata:
        return None
    diagnostics = {key: metadata[key] for key in _DIAGNOSTIC_KEYS if key in metadata}
    return diagnostics or None

# (db, request) -> kurulu DigestGenerator. send_notification gating'i factory'de.
GeneratorFactory = Callable[[AsyncSession, DigestRequest], Awaitable[DigestGenerator]]


class AiEngineDigestRunner:
    """`DigestGenerator.generate`'i koşturup `digests.status`'u `DigestRunResult`'a çevirir."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        generator_factory: GeneratorFactory,
    ) -> None:
        self._session_factory = session_factory
        self._generator_factory = generator_factory

    async def run(self, request: DigestRequest) -> DigestRunResult:
        async with self._session_factory() as db:
            try:
                newsletter = await db.scalar(
                    select(NewsletterTemplate)
                    .options(selectinload(NewsletterTemplate.sections))
                    .where(NewsletterTemplate.id == request.newsletter_template_id)
                )
                if newsletter is None:
                    return DigestRunResult(
                        status=DigestStatus.FAILED,
                        error="Bülten şablonu bulunamadı.",
                    )
                generator = await self._generator_factory(db, request)
                digest = await generator.generate(
                    db,
                    newsletter=newsletter,
                    period_start=request.period_start,
                    period_end=request.period_end,
                    actor_user_id=request.actor_user_id,
                )
                await db.commit()
                status = (
                    DigestStatus.READY
                    if digest.status == DigestStatus.READY
                    else DigestStatus.FAILED
                )
                # `digest.sections` lazy relationship'i async session'da implicit IO
                # tetikler (MissingGreenlet); bölüm sayısını açık count ile al.
                section_count = int(
                    await db.scalar(
                        select(func.count())
                        .select_from(DigestSection)
                        .where(DigestSection.digest_id == digest.id)
                    )
                    or 0
                )
                return DigestRunResult(
                    status=status,
                    digest_id=digest.id,
                    section_count=section_count,
                    diagnostics=_diagnostics_from_metadata(digest.generation_metadata),
                )
            except DigestGenerationError as exc:
                # `generate` digest'i `failed` işaretledi (flush); commit ile kalıcılaştır.
                await db.commit()
                return DigestRunResult(status=DigestStatus.FAILED, error=str(exc))
            except Exception:
                await db.rollback()
                logger.exception(
                    "pipeline_digest_generation_unexpected_error",
                    extra={"newsletter_template_id": str(request.newsletter_template_id)},
                )
                return DigestRunResult(
                    status=DigestStatus.FAILED,
                    error="Bülten üretimi sırasında beklenmeyen hata oluştu.",
                )
