"""Aşama yürütücü sözleşmesi + İterasyon 2 stub executor'ları (Faz 6.1).

Her pipeline aşaması bir `StageExecutor`'dır: orkestratör `run(run, step)` çağırır,
geri dönen `StepResult` ile step sayaçlarını/durumunu kalıcılaştırır. Gerçek invoke
(collect/ingest → İter 3, process → İter 4, digest → İter 5) bu dosyada stub'ların
yerini alır; sözleşme değişmez (`Docs/04` §10.5).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any, Protocol

from packages.shared.enums import (
    DigestStatus,
    DigestType,
    PipelineStage,
    PipelineStepStatus,
)

from services.orchestrator.aws_clients import (
    CollectorInvoker,
    LambdaInvoker,
    QueueDepth,
    SqsObserver,
)

if TYPE_CHECKING:
    from packages.shared.models.pipeline_run import PipelineRun
    from packages.shared.models.pipeline_run_step import PipelineRunStep

logger = logging.getLogger("ygip.orchestrator.stages")

# Manuel pipeline'da invoke edilebilen collector tipleri (`Docs/04` §7 COLLECTOR_MAP).
# `["all"]` yalnızca bu kümeyle kesişen aktif tiplere genişletilir.
COLLECTOR_SOURCE_TYPES: tuple[str, ...] = ("rss", "email", "gov")


@dataclass(slots=True)
class StepResult:
    """Bir aşama yürütmesinin sonucu — orkestratör step durumunu buradan türetir.

    `status` step seviyesi sonucu (`completed`/`failed`). Step enum'unda `partial`
    yoktur; kaynak/aşama seviyesi kısmi başarı `degraded=True` ile işaretlenir ve
    run seviyesine `partial` olarak yansır (`Docs/01` §5.5). `abort=True` kritik
    aşama hatasıdır: sonraki aşamalar `skipped`, run `failed`.
    """

    status: PipelineStepStatus
    items_in: int = 0
    items_out: int = 0
    items_failed: int = 0
    detail: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    degraded: bool = False
    abort: bool = False

    @classmethod
    def completed(
        cls,
        *,
        items_in: int = 0,
        items_out: int = 0,
        items_failed: int = 0,
        detail: dict[str, Any] | None = None,
        degraded: bool = False,
    ) -> StepResult:
        return cls(
            status=PipelineStepStatus.COMPLETED,
            items_in=items_in,
            items_out=items_out,
            items_failed=items_failed,
            detail=detail or {},
            degraded=degraded,
        )

    @classmethod
    def failed(
        cls,
        error: str,
        *,
        items_in: int = 0,
        items_out: int = 0,
        items_failed: int = 0,
        detail: dict[str, Any] | None = None,
        abort: bool = False,
    ) -> StepResult:
        return cls(
            status=PipelineStepStatus.FAILED,
            items_in=items_in,
            items_out=items_out,
            items_failed=items_failed,
            detail=detail or {},
            error=error,
            abort=abort,
        )


class StageExecutor(Protocol):
    """Aşama yürütücü sözleşmesi (`Docs/04` §10.5)."""

    stage: PipelineStage

    async def run(self, run: PipelineRun, step: PipelineRunStep) -> StepResult:
        """Aşamayı yürüt; sayaç + detail + hata içeren `StepResult` döndür."""
        ...


class StubStageExecutor:
    """İterasyon 2 placeholder — sabit/parametrik `StepResult` döndürür.

    İterasyon 3–5'te ilgili gerçek executor (Collect/Ingest/Process/Digest) bu
    stub'ın yerini alır. Test/geliştirme için `result` enjekte edilebilir.
    """

    def __init__(self, stage: PipelineStage, result: StepResult | None = None) -> None:
        self.stage = stage
        self._result = result

    async def run(self, run: PipelineRun, step: PipelineRunStep) -> StepResult:
        if self._result is not None:
            return self._result
        return StepResult.completed(detail={"stub": True, "stage": self.stage.value})


def build_stub_executors() -> dict[PipelineStage, StageExecutor]:
    """4 aşama için varsayılan stub executor haritası (İterasyon 2)."""
    return {stage: StubStageExecutor(stage) for stage in PipelineStage}


# --- İterasyon 3: Collect + Ingest gerçek adapter'ları ----------------------


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


class CollectStageExecutor:
    """`run.source_types` collector Lambda'larını boto3 ile invoke eder (`Docs/04` §10.5).

    `["all"]` → aktif tiplerle kesişen `COLLECTOR_SOURCE_TYPES`'a genişler (pasif/error
    kaynaklar collector içinde atlanır — `Docs/01` source rules). Kaynak bazlı ok/failed
    `StepResult.detail`'e yazılır; request id'ler teşhis için saklanır. Bir tip başarısız
    ama en az biri başarılıysa `degraded` (run `partial`); **tüm** invoke'lar başarısız
    veya hiç tip yoksa `abort` (kritik: hiç kaynak toplanmadı → run `failed`).
    """

    stage = PipelineStage.COLLECT

    def __init__(
        self,
        *,
        invoker: CollectorInvoker | None = None,
        active_types_resolver: Callable[[], Awaitable[list[str]]] | None = None,
    ) -> None:
        self._invoker = invoker or LambdaInvoker()
        self._resolve_active = active_types_resolver

    async def _resolve_types(self, run: PipelineRun) -> list[str]:
        requested = [t.lower() for t in run.source_types]
        if "all" in requested:
            if self._resolve_active is not None:
                active = [t.lower() for t in await self._resolve_active()]
            else:
                active = list(COLLECTOR_SOURCE_TYPES)
            candidates = [t for t in active if t in COLLECTOR_SOURCE_TYPES]
        else:
            candidates = [t for t in requested if t in COLLECTOR_SOURCE_TYPES]
        return _dedupe_preserve_order(candidates)

    async def run(self, run: PipelineRun, step: PipelineRunStep) -> StepResult:
        types = await self._resolve_types(run)
        if not types:
            return StepResult.failed(
                "Toplanacak aktif kaynak tipi yok",
                abort=True,
                detail={"requested": list(run.source_types)},
            )

        detail: dict[str, Any] = {}
        published = 0
        failed_sources = 0
        empty_sources = 0
        ok_types = 0
        for source_type in types:
            result = await self._invoker.invoke_collector(source_type)
            if result.ok:
                ok_types += 1
                body = result.payload or {}
                count = int(body.get("published", 0))
                processed = int(body.get("sources_processed", 0))
                source_failed = int(body.get("sources_failed", 0))
                source_empty = int(body.get("sources_empty", 0))
                published += count
                failed_sources += source_failed
                empty_sources += source_empty
                detail[source_type] = {
                    "ok": True,
                    "published": count,
                    "sources_processed": processed,
                    "sources_failed": source_failed,
                    # Çekim başarılı ama 0 içerik düşen kaynaklar — dejenere/yanlış
                    # konfigürasyon işareti; kokpitte görünür kılınır.
                    "sources_empty": source_empty,
                    "request_id": result.request_id,
                }
            else:
                detail[source_type] = {
                    "ok": False,
                    "error": result.error,
                    "request_id": result.request_id,
                }

        if ok_types == 0:
            return StepResult.failed(
                "Tüm collector invoke'ları başarısız",
                abort=True,
                items_failed=len(types),
                detail=detail,
            )

        if empty_sources:
            detail["sources_empty"] = empty_sources

        degraded = ok_types < len(types) or failed_sources > 0
        return StepResult.completed(
            items_in=0,
            items_out=published,
            items_failed=failed_sources,
            detail=detail,
            degraded=degraded,
        )


class RawItemCounter(Protocol):
    """Ingest gözlemi için bu run'a ait `raw_items` sayımı sözleşmesi (test mock'u)."""

    async def count_ingested(self, run: PipelineRun) -> int: ...


class IngestStageExecutor:
    """`raw_items` artışını gözlemleyerek ingest aşamasını tamamlar (`Docs/04` §10.5).

    Invoke yok — collect SQS'e yayınlar, SQS consumer `raw_items` yazar; bu aşama yalnızca
    bu run'a ait `raw_items` sayısını (`fetched_at >= run.started_at`) collect'in beklenen
    sayısına (`collect.items_out`) erişene **veya** artış durana (stabilizasyon) **veya**
    timeout'a kadar poll eder (sonsuz bekleme yok). Eksik kalan = `items_failed` → `degraded`
    (run `partial`); aşamayı `abort` etmez (processor gecikmesi run'ı düşürmemeli).
    """

    stage = PipelineStage.INGEST

    def __init__(
        self,
        *,
        counter: RawItemCounter,
        poll_interval: float = 2.0,
        max_polls: int = 15,
        stable_polls: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._counter = counter
        self._poll_interval = poll_interval
        self._max_polls = max_polls
        self._stable_polls = stable_polls
        self._sleep = sleep

    @staticmethod
    def _expected_from_collect(run: PipelineRun) -> int:
        for step in run.steps:
            if step.stage == PipelineStage.COLLECT:
                return max(0, int(step.items_out or 0))
        return 0

    async def run(self, run: PipelineRun, step: PipelineRunStep) -> StepResult:
        expected = self._expected_from_collect(run)
        observed = 0
        previous = -1
        stable = 0
        polls = 0
        while polls < self._max_polls:
            polls += 1
            observed = await self._counter.count_ingested(run)
            if expected and observed >= expected:
                break
            if observed == previous:
                stable += 1
                if stable >= self._stable_polls:
                    break
            else:
                stable = 0
            previous = observed
            await self._sleep(self._poll_interval)

        items_failed = max(0, expected - observed) if expected else 0
        detail = {"expected": expected, "observed": observed, "polls": polls}
        return StepResult.completed(
            items_in=expected,
            items_out=observed,
            items_failed=items_failed,
            detail=detail,
            degraded=items_failed > 0,
        )


# --- İterasyon 4: Process gerçek adapter'ı (SQS + processed gözlem) ----------


class ProcessedItemCounter(Protocol):
    """Process gözlemi için bu run'a ait `processed_items` toplam sayım sözleşmesi."""

    async def count_processed(self, run: PipelineRun) -> int: ...


class RawItemFailedCounter(Protocol):
    """Bu run'da `FAILED` işaretli `raw_items` (gerçek hata) sayım sözleşmesi."""

    async def count_failed(self, run: PipelineRun) -> int: ...


class ProcessStageExecutor:
    """SQS drain + `processed_items` artışı ile process aşamasını tamamlar (`Docs/04` §10.5).

    Invoke yok — processor Lambda'ları SQS'i kendi tüketir; bu aşama yalnızca **gözlemler**.
    İlgili tip queue'larının (collect step'inin invoke ettiği tipler) görünür + uçuşta mesaj
    sayısı 0 **ve** `processed_items` artışı `stable_polls` boyunca durana kadar poll eder;
    yalnız queue sayısına güvenmez — at-least-once `Approximate*` yaklaşıktır, processed
    delta ile **çapraz doğrulanır** (`Docs/04` §8 risk). `max_polls`/timeout ile sonsuz
    bekleme yok.

    Sayaç anlamı (`Docs/04` §10.5): items_out = işlenen (`processed_items` yazılan);
    items_failed = **gerçek hata** (raw_items `FAILED` + DLQ) — filtreleme dahil DEĞİL.
    Beklenen (ingested) − işlenen − hata farkı, gate/dedup ile **elenen** içeriktir ve
    `detail["filtered"]`'a yazılır (hata değil; `Docs/04` §8.3 keyword gate). Drain
    olmadan timeout olursa fark "elendi" değil `detail["pending"]`'dir (akıbeti belirsiz).
    `degraded` yalnızca gerçek hata / DLQ / timeout'ta True — filtreleme tek başına run'ı
    `partial` yapmaz. Kritik değil → `abort` etmez.
    """

    stage = PipelineStage.PROCESS

    def __init__(
        self,
        *,
        observer: SqsObserver,
        counter: ProcessedItemCounter,
        failed_counter: RawItemFailedCounter | None = None,
        poll_interval: float = 5.0,
        max_polls: int = 60,
        stable_polls: int = 2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._observer = observer
        self._counter = counter
        self._failed_counter = failed_counter
        self._poll_interval = poll_interval
        self._max_polls = max_polls
        self._stable_polls = stable_polls
        self._sleep = sleep

    @staticmethod
    def _observed_types(run: PipelineRun) -> list[str]:
        """İzlenecek queue tipleri — collect step detail'inden (genişletilmiş `all` dahil)."""
        for step in run.steps:
            if step.stage == PipelineStage.COLLECT and step.detail:
                keys = [k for k in step.detail if k in COLLECTOR_SOURCE_TYPES]
                if keys:
                    return _dedupe_preserve_order(keys)
        requested = [t.lower() for t in run.source_types]
        if "all" in requested:
            return list(COLLECTOR_SOURCE_TYPES)
        return _dedupe_preserve_order(
            [t for t in requested if t in COLLECTOR_SOURCE_TYPES]
        )

    @staticmethod
    def _expected_from_ingest(run: PipelineRun) -> int:
        for step in run.steps:
            if step.stage == PipelineStage.INGEST:
                return max(0, int(step.items_out or 0))
        return 0

    async def run(self, run: PipelineRun, step: PipelineRunStep) -> StepResult:
        types = self._observed_types(run)
        expected = self._expected_from_ingest(run)
        processed = 0
        previous = -1
        stable = 0
        polls = 0
        depths: dict[str, QueueDepth] = {}
        drained = False
        while polls < self._max_polls:
            polls += 1
            processed = await self._counter.count_processed(run)
            depths = {t: await self._observer.queue_depth(t) for t in types}
            drained = all(d.is_drained for d in depths.values()) if depths else True

            if processed == previous:
                stable += 1
            else:
                stable = 0
            previous = processed

            # Drain + processed delta durağan (çapraz doğrulama) → tamam.
            if drained and stable >= self._stable_polls:
                break
            # Beklenen işlenmiş + queue boş → erken çıkış.
            if expected and processed >= expected and drained:
                break
            await self._sleep(self._poll_interval)

        dlq_total = sum(d.dlq for d in depths.values())
        timed_out = not drained

        # Gerçek hata = processor exception/persist hatası (raw_items FAILED) + DLQ.
        real_failed = 0
        if self._failed_counter is not None:
            real_failed = await self._failed_counter.count_failed(run)
        errors = real_failed + dlq_total

        # Kalan fark: drain olduysa gate/dedup ile **elendi**; timeout'ta akıbeti
        # belirsiz → "pending" (elendi sayma — yanıltıcı olur).
        remainder = max(0, expected - processed - errors) if expected else 0
        filtered = 0 if timed_out else remainder
        pending = remainder if timed_out else 0

        detail: dict[str, Any] = {
            "expected": expected,
            "processed": processed,
            "filtered": filtered,
            "errors": errors,
            "pending": pending,
            "drain_polls": polls,
            "drained": drained,
            "dlq": dlq_total,
            "queues": {
                t: {"visible": d.visible, "not_visible": d.not_visible, "dlq": d.dlq}
                for t, d in depths.items()
            },
        }
        return StepResult.completed(
            items_in=expected,
            items_out=processed,
            items_failed=errors,
            detail=detail,
            degraded=errors > 0 or timed_out,
        )


# --- İterasyon 5: Digest gerçek adapter'ı (mevcut digest üretimini çağırır) --


@dataclass(slots=True)
class DigestRequest:
    """`run.params`'tan türeyen digest üretim isteği (`Docs/03` §7)."""

    digest_type: DigestType
    period_start: date
    period_end: date
    send_notification: bool
    actor_user_id: uuid.UUID | None


@dataclass(slots=True)
class DigestRunResult:
    """Digest üretim sonucu — `digests.status` step'e bu yapıyla yansır (`Docs/01` §5.3)."""

    status: DigestStatus
    digest_id: uuid.UUID | None = None
    section_count: int = 0
    error: str | None = None


class DigestRunner(Protocol):
    """Mevcut digest üretim akışını çalıştıran sözleşme (`Docs/04` §9).

    Gerçek implementasyon (`AiEngineDigestRunner`) `DigestGenerator`'ı kendi DB
    session'ında koşturur; iş mantığı yeniden yazılmaz — yalnızca çağrılır.
    Testlerde mock'lanır (gerçek LLM çağrısı yok).
    """

    async def run(self, request: DigestRequest) -> DigestRunResult: ...


class DigestStageExecutor:
    """Mevcut digest üretimini çağırır; `digests.status`'u step'e yansıtır (`Docs/04` §10.5).

    `run.params`'tan digest_type/period/send_notification okunur (`Docs/03` §7); runner
    `DigestGenerator`'ı koşturur (yeniden yazma yok). `ready`→`completed`, `failed`→
    `failed` + `abort` (digest deliverable; üretilemezse run `failed` — `Docs/01` §5.5
    quality gate). Üretilen `digest_id` step `detail`'ine ve `run.stats`'a yazılır;
    `digest_update` run'ında collect/ingest/process baştan `skipped` olduğundan yalnızca
    bu aşama koşar.
    """

    stage = PipelineStage.DIGEST

    def __init__(self, *, runner: DigestRunner) -> None:
        self._runner = runner

    @staticmethod
    def _parse_request(run: PipelineRun) -> DigestRequest:
        params = run.params or {}
        digest_type = DigestType(params["digest_type"])
        period_start = date.fromisoformat(str(params["period_start"]))
        period_end = date.fromisoformat(str(params["period_end"]))
        if period_end < period_start:
            raise ValueError("period_end, period_start tarihinden önce olamaz")
        return DigestRequest(
            digest_type=digest_type,
            period_start=period_start,
            period_end=period_end,
            send_notification=bool(params.get("send_notification", False)),
            actor_user_id=run.triggered_by,
        )

    async def run(self, run: PipelineRun, step: PipelineRunStep) -> StepResult:
        try:
            request = self._parse_request(run)
        except (KeyError, ValueError, TypeError) as exc:
            return StepResult.failed(
                f"Geçersiz digest parametreleri: {exc}",
                abort=True,
                detail={"params": dict(run.params or {})},
            )

        result = await self._runner.run(request)
        digest_id = str(result.digest_id) if result.digest_id is not None else None
        detail: dict[str, Any] = {
            "digest_id": digest_id,
            "digest_type": request.digest_type.value,
            "period_start": request.period_start.isoformat(),
            "period_end": request.period_end.isoformat(),
            "section_count": result.section_count,
            "send_notification": request.send_notification,
        }
        if digest_id is not None:
            # JSONB in-place mutasyon izlenmez — yeniden ata ki commit'te kalıcılaşsın.
            run.stats = {**(run.stats or {}), "digest_id": digest_id}

        if result.status == DigestStatus.READY:
            return StepResult.completed(items_out=result.section_count, detail=detail)
        return StepResult.failed(
            result.error or "Bülten üretimi başarısız",
            abort=True,
            detail=detail,
        )


def build_collect_ingest_executors(
    *,
    invoker: CollectorInvoker | None = None,
    counter: RawItemCounter,
    active_types_resolver: Callable[[], Awaitable[list[str]]] | None = None,
    sqs_observer: SqsObserver | None = None,
    processed_counter: ProcessedItemCounter | None = None,
    failed_counter: RawItemFailedCounter | None = None,
    digest_runner: DigestRunner | None = None,
) -> dict[PipelineStage, StageExecutor]:
    """Gerçek Collect+Ingest+Process+Digest aşama haritası.

    `sqs_observer` ve `processed_counter` verilirse gerçek `ProcessStageExecutor`
    bağlanır; aksi halde Process stub kalır (geriye uyumlu). `failed_counter`
    verilirse Process adımı "Hatalı" (gerçek hata) ile "Elendi" (filtreleme) ayrımını
    yapar. `digest_runner` verilirse gerçek `DigestStageExecutor` bağlanır; aksi halde
    Digest stub kalır (İter 2 davranışı).
    """
    process_executor: StageExecutor = (
        ProcessStageExecutor(
            observer=sqs_observer,
            counter=processed_counter,
            failed_counter=failed_counter,
        )
        if sqs_observer is not None and processed_counter is not None
        else StubStageExecutor(PipelineStage.PROCESS)
    )
    digest_executor: StageExecutor = (
        DigestStageExecutor(runner=digest_runner)
        if digest_runner is not None
        else StubStageExecutor(PipelineStage.DIGEST)
    )
    return {
        PipelineStage.COLLECT: CollectStageExecutor(
            invoker=invoker, active_types_resolver=active_types_resolver
        ),
        PipelineStage.INGEST: IngestStageExecutor(counter=counter),
        PipelineStage.PROCESS: process_executor,
        PipelineStage.DIGEST: digest_executor,
    }
