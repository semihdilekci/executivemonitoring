"""Yerel (in-process) pipeline runtime — AWS Lambda/SQS olmadan collect + process.

Üretimde COLLECT aşaması collector Lambda'larını invoke eder, processor Lambda'ları
SQS'i tüketip `raw_items`/`processed_items` yazar (`Docs/04` §8, §10.5). Yerel
geliştirmede Lambda/SQS yoktur; bu modül aynı **iş mantığını** (collector batch +
processor pipeline) tek süreçte çalıştıran adapter'lar sağlar:

* `LocalCollectorInvoker` — `CollectorInvoker` sözleşmesini karşılar. Gerçek collector
  batch'ini çalıştırır, yayınlanan makaleleri SQS yerine bellekte yakalar ve processor
  pipeline'ından geçirerek `raw_items` + `processed_items` + `content_chunks` yazar.
* `LocalSqsObserver` — `SqsObserver` sözleşmesini karşılar. SQS olmadığından kuyruk
  daima boş (drained) raporlanır; process aşaması `processed_items` artışını gözleyerek
  tamamlanır.

Collector/processor iş mantığı **değişmez** — yalnızca invoke yolu in-process'e taşınır
(`Docs/10` §6.1 Don'ts). `PIPELINE_RUNTIME_MODE=local` ile devreye girer (`pipeline_driver`).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from packages.shared.models.source import Source
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from services.collectors.handler import run_collector_batch
from services.collectors.source_loader import load_active_sources
from services.collectors.sqs_publisher import SQSPublisher
from services.orchestrator.aws_clients import InvokeResult, QueueDepth
from services.processor.db_session import create_processor_redis
from services.processor.models import ProcessorInput
from services.processor.pipeline_orchestrator import (
    PipelineOrchestrator,
    build_translation_dependencies,
)

logger = logging.getLogger("ygip.orchestrator.local")

SourcesLoader = Callable[[str], Awaitable[list[Source]]]
RedisFactory = Callable[[], Awaitable[Redis]]


class _CapturingSqsClient:
    """Sahte boto3 SQS istemcisi — `send_message` gövdeyi yakalar, ağa çıkmaz.

    `SQSPublisher` ile aynı serileştirmeyi (collector→processor sözleşmesi) kullanmak
    için gerçek publisher'a enjekte edilir; böylece mesaj formatı üretimle bire bir aynı.
    """

    def __init__(self) -> None:
        self.bodies: list[str] = []

    def send_message(self, *, QueueUrl: str, MessageBody: str) -> dict[str, str]:  # noqa: N803
        del QueueUrl
        self.bodies.append(MessageBody)
        return {"MessageId": f"local-{len(self.bodies)}"}


class LocalCollectorInvoker:
    """Collector Lambda invoke yerine collector+processor'ı in-process çalıştırır.

    `invoke_collector(source_type)`:
      1. Aktif kaynakları yükler, gerçek collector batch'ini çalıştırır.
      2. Yayınlanacak makaleleri SQS yerine bellekte yakalar.
      3. Her makaleyi processor pipeline'ından geçirir → `raw_items` + `processed_items`
         + `content_chunks` yazar (idempotent ingest + dedup processor içinde).

    Dönen `InvokeResult.payload`, `CollectStageExecutor`'ın beklediği `published`/
    `sources_processed`/`sources_failed` sayaçlarını taşır (üretim Lambda yanıtıyla aynı).
    """

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        sources_loader: SourcesLoader = load_active_sources,
        redis_factory: RedisFactory = create_processor_redis,
    ) -> None:
        self._session_factory = session_factory
        self._load_sources = sources_loader
        self._redis_factory = redis_factory

    async def invoke_collector(self, source_type: str) -> InvokeResult:
        try:
            sources = await self._load_sources(source_type)
        except Exception as exc:  # geçersiz tip / DB hatası → aşama bu tipi failed sayar
            logger.warning(
                "local_sources_load_failed",
                extra={"source_type": source_type, "error": str(exc)},
            )
            return InvokeResult(
                ok=False, source_type=source_type, error=f"kaynak yükleme: {exc}"
            )

        capture = _CapturingSqsClient()
        publisher = SQSPublisher(sqs_client=capture)
        # URL-cache: tam metin sayfalarının her run'da yeniden indirilmesini önler.
        redis = await self._redis_factory()
        try:
            results = await run_collector_batch(
                source_type, sources, publisher, redis_client=redis
            )
        except Exception as exc:
            logger.exception(
                "local_collector_batch_failed", extra={"source_type": source_type}
            )
            return InvokeResult(ok=False, source_type=source_type, error=str(exc))
        finally:
            await redis.aclose()

        processed_local = await self._process_bodies(capture.bodies)
        payload = {
            "published": int(results.get("published", 0)),
            "sources_processed": int(results.get("sources_processed", 0)),
            "sources_failed": int(results.get("sources_failed", 0)),
            "processed_local": processed_local,
        }
        logger.info(
            "local_collect_invoke_done",
            extra={"source_type": source_type, **payload},
        )
        return InvokeResult(
            ok=True,
            source_type=source_type,
            status_code=200,
            payload=payload,
        )

    async def _process_bodies(self, bodies: list[str]) -> int:
        """Yakalanan SQS gövdelerini processor pipeline'ından geçirir (mesaj başına commit).

        Her mesaj kendi session'ında işlenir → bir mesajın hatası diğerlerini geri almaz
        (üretimdeki SQS kayıt-başına işleme davranışıyla aynı). Redis dedup için yeniden
        kullanılır.
        """
        if not bodies:
            return 0

        redis = await self._redis_factory()
        processed = 0
        try:
            for body in bodies:
                item = ProcessorInput.from_sqs_body(body)
                async with self._session_factory() as session:
                    # İngilizce haber çevirisi için operasyon-scoped LLM client + eşik
                    # (Lambda `handle_sqs_event` ile aynı bağlama; `Docs/04` §8.45/§9.1).
                    # Aktif `article_translation` anahtarı yoksa client None → no-op.
                    translation_client, translation_min_score = (
                        await build_translation_dependencies(session)
                    )
                    orchestrator = PipelineOrchestrator(
                        session=session,
                        redis=redis,
                        translation_llm_client=translation_client,
                        translation_min_score=translation_min_score,
                    )
                    try:
                        result = await orchestrator.process(item, sqs_body=body)
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        logger.exception("local_process_item_failed")
                        continue
                    if result.status == "success":
                        processed += 1
        finally:
            await redis.aclose()
        return processed


class LocalSqsObserver:
    """Yerel runtime SQS gözlemi — kuyruk yok, processor in-process bittiği için daima boş.

    Process aşaması yalnızca `processed_items` artışını gözleyerek tamamlanır; kuyruk
    derinliği her zaman drained (0) raporlanır.
    """

    async def queue_depth(self, source_type: str) -> QueueDepth:
        return QueueDepth(source_type=source_type, visible=0, not_visible=0, dlq=0)
