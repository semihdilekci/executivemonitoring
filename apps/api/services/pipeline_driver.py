"""Pipeline background driver — orkestratörü gerçek aşama adapter'larıyla sürer (Faz 6.1).

`apps/api` katmanına özgü bağımlılıklar (LLM key servisleri, digest generator, notification)
yalnızca burada bağlanır; `services/orchestrator` paketi `apps/api`'ye bağımlı kalmaz.
Orkestratör kendi `session_factory`'sini kullanır (request lifecycle'ından bağımsız —
`Docs/04` §10.5). Driver bittiğinde `pipeline.completed`/`pipeline.failed` audit'i yazılır
(`Docs/07` §9.1). Collector/processor/ai-engine iş mantığı değişmez — yalnızca invoke +
gözlem (`Docs/10` §6.1 Don'ts).
"""

from __future__ import annotations

import logging
import uuid

from packages.shared.enums import PipelineRunStatus
from packages.shared.models.digest import Digest
from services.ai_engine.digest_generator import DigestGenerator
from services.orchestrator import (
    AiEngineDigestRunner,
    BotoSqsObserver,
    DbActiveTypesResolver,
    DbProcessedItemCounter,
    DbRawItemCounter,
    DigestRequest,
    LambdaInvoker,
    LocalCollectorInvoker,
    LocalSqsObserver,
    PipelineOrchestrator,
    build_collect_ingest_executors,
    get_orchestrator_aws_settings,
    run_repository,
)
from services.orchestrator.aws_clients import CollectorInvoker, SqsObserver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.services.api_key_service import ApiKeyService
from apps.api.services.api_usage_service import ApiUsageService
from apps.api.services.audit_service import AuditService
from apps.api.services.llm_client_factory import build_llm_client
from apps.api.services.notification_service import notification_service
from apps.api.services.prompt_template_resolver import db_prompt_template_resolver

logger = logging.getLogger("ygip.api.pipeline_driver")

# Nihai run durumu → audit event tipi (`Docs/07` §9.1). `cancelled` API'de audit edildi.
_COMPLETION_EVENT: dict[PipelineRunStatus, str] = {
    PipelineRunStatus.COMPLETED: "pipeline.completed",
    PipelineRunStatus.PARTIAL: "pipeline.completed",
    PipelineRunStatus.FAILED: "pipeline.failed",
}


def _build_orchestrator(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    api_key_service: ApiKeyService,
    api_usage_service: ApiUsageService,
) -> PipelineOrchestrator:
    aws_settings = get_orchestrator_aws_settings()

    async def generator_factory(
        db: AsyncSession, request: DigestRequest
    ) -> DigestGenerator:
        llm_client = await build_llm_client(db, api_key_service, api_usage_service)

        async def notification_hook(
            session: AsyncSession,
            digest: Digest,
            success: bool,
            _error_message: str | None,
        ) -> None:
            # `send_notification=false` (test modu) → mail/push gitmez (`Docs/06`).
            if success and request.send_notification:
                await notification_service.send_digest_ready(session, digest=digest)

        return DigestGenerator(
            llm_client=llm_client,
            template_resolver=db_prompt_template_resolver,
            notification_hook=notification_hook,
        )

    # Çalışma modu: "local" → collector+processor in-process (AWS/SQS gerektirmez,
    # yerel geliştirme); aksi halde Lambda invoke + SQS gözlemi (`Docs/04` §10.5).
    if aws_settings.PIPELINE_RUNTIME_MODE.strip().lower() == "local":
        invoker: CollectorInvoker = LocalCollectorInvoker(session_factory=session_factory)
        sqs_observer: SqsObserver = LocalSqsObserver()
    else:
        invoker = LambdaInvoker(settings=aws_settings)
        sqs_observer = BotoSqsObserver(settings=aws_settings)

    executors = build_collect_ingest_executors(
        invoker=invoker,
        counter=DbRawItemCounter(session_factory),
        active_types_resolver=DbActiveTypesResolver(session_factory),
        sqs_observer=sqs_observer,
        processed_counter=DbProcessedItemCounter(session_factory),
        digest_runner=AiEngineDigestRunner(
            session_factory=session_factory,
            generator_factory=generator_factory,
        ),
    )
    return PipelineOrchestrator(session_factory=session_factory, executors=executors)


async def schedule_pipeline_run(
    *,
    run_id: uuid.UUID,
    session_factory: async_sessionmaker[AsyncSession],
    api_key_service: ApiKeyService,
    api_usage_service: ApiUsageService,
    audit_service: AuditService,
) -> None:
    """Run'ı uçtan uca sür ve nihai duruma göre audit yaz. Hata yutulur (background)."""
    try:
        orchestrator = _build_orchestrator(
            session_factory=session_factory,
            api_key_service=api_key_service,
            api_usage_service=api_usage_service,
        )
        final_status = await orchestrator.drive(run_id)
    except Exception:
        logger.exception("pipeline_driver_failed", extra={"run_id": str(run_id)})
        return

    event_type = _COMPLETION_EVENT.get(final_status)
    if event_type is None:
        return
    try:
        async with session_factory() as db:
            run = await run_repository.get_run(db, run_id)
            if run is None:
                return
            await audit_service.log_event(
                db,
                event_type=event_type,
                actor_user_id=run.triggered_by,
                target_type="pipeline_run",
                target_id=run.id,
                payload={
                    "run_type": run.run_type.value,
                    "status": final_status.value,
                },
            )
            await db.commit()
    except Exception:
        logger.exception(
            "pipeline_driver_audit_failed", extra={"run_id": str(run_id)}
        )
