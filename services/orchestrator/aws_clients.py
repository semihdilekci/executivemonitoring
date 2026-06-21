"""Boto3 AWS istemci sarmalayıcıları — orkestratör invoke/gözlem adapter'ları (Faz 6.1).

Collector Lambda **senkron invoke** (`lambda:InvokeFunction`, İter 3) ve process aşaması
SQS **gözlemi** (`sqs:GetQueueAttributes`, İter 4) için ince bir boto3 katmanı. Burada
**iş mantığı yoktur**: yalnızca isim/ARN çözümleme + senkron boto3 çağrısını thread'e taşıma
+ yanıt parse. Collector/processor iş mantığına dokunulmaz — yalnızca invoke edilir / queue
derinliği okunur (`Docs/04` §10.5, `Docs/10` §6.1 Don'ts).

Tüm çağrılar mock'lanabilir (`CollectorInvoker` Protocol) — testler gerçek AWS'e çıkmaz,
credential gerektirmez (`Docs/08` §3.6).

> **Kaynak adı:** Gerçek collector Lambda'sı CDK'da `dev-ygip-collector-{type}` olarak
> deploy edilir (`infra/ygip_infra/config.py` `resource_name`). Varsayılan şablon bunu
> izler; ortam başına `ORCH_COLLECTOR_FN_{TYPE}` ile birebir override edilebilir
> (`Docs/04` §12 environment-scoped, `30-infra-aws.mdc`).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Protocol

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("ygip.orchestrator.aws")


class OrchestratorAwsSettings(BaseSettings):
    """Orkestratör AWS kaynak çözümleme ayarları (env-scoped)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    AWS_REGION: str = "eu-west-1"

    # Pipeline çalışma modu: "aws" (Lambda/SQS invoke+gözlem) veya "local" (collector +
    # processor in-process; AWS gerektirmez — yerel geliştirme için, `Docs/04` §10.5).
    PIPELINE_RUNTIME_MODE: str = "aws"

    # Gerçek deploy adıyla aynı: `dev-ygip-collector-rss` (`infra` config.py).
    ORCH_RESOURCE_PREFIX: str = "dev-ygip"
    ORCH_COLLECTOR_FN_TEMPLATE: str = "{prefix}-collector-{source_type}"
    ORCH_INVOKE_TIMEOUT_SECONDS: float = 120.0

    # Opsiyonel: tip başına tam fonksiyon adı override (boşsa şablon kullanılır).
    ORCH_COLLECTOR_FN_RSS: str = ""
    ORCH_COLLECTOR_FN_EMAIL: str = ""
    ORCH_COLLECTOR_FN_GOV: str = ""

    # Process aşaması SQS gözlemi (İter 4). Queue adı `infra` `sqs_queue_name` ile
    # aynı: `dev-ygip-sqs-rss` / `-dlq` (`Docs/04` §8, §12). URL override verilirse
    # `sqs:GetQueueUrl` çözümü atlanır.
    ORCH_SQS_QUEUE_NAME_TEMPLATE: str = "{prefix}-sqs-{source_type}"
    ORCH_SQS_DLQ_NAME_TEMPLATE: str = "{prefix}-sqs-{source_type}-dlq"
    ORCH_SQS_QUEUE_RSS_URL: str = ""
    ORCH_SQS_QUEUE_EMAIL_URL: str = ""
    ORCH_SQS_QUEUE_GOV_URL: str = ""
    ORCH_PROCESS_POLL_INTERVAL_SECONDS: float = 5.0
    ORCH_PROCESS_MAX_POLLS: int = 60
    ORCH_PROCESS_STABLE_POLLS: int = 2

    def collector_function_name(self, source_type: str) -> str:
        """`source_type` → collector Lambda fonksiyon adı (`Docs/04` §7, §12)."""
        override = {
            "rss": self.ORCH_COLLECTOR_FN_RSS,
            "email": self.ORCH_COLLECTOR_FN_EMAIL,
            "gov": self.ORCH_COLLECTOR_FN_GOV,
        }.get(source_type, "")
        if override:
            return override
        return self.ORCH_COLLECTOR_FN_TEMPLATE.format(
            prefix=self.ORCH_RESOURCE_PREFIX, source_type=source_type
        )

    def queue_name_for_source_type(self, source_type: str) -> str:
        """`source_type` → ana SQS queue adı (`Docs/04` §8; `infra` `sqs_queue_name`)."""
        return self.ORCH_SQS_QUEUE_NAME_TEMPLATE.format(
            prefix=self.ORCH_RESOURCE_PREFIX, source_type=source_type
        )

    def dlq_name_for_source_type(self, source_type: str) -> str:
        """`source_type` → DLQ queue adı (`infra` `sqs_dlq_name`)."""
        return self.ORCH_SQS_DLQ_NAME_TEMPLATE.format(
            prefix=self.ORCH_RESOURCE_PREFIX, source_type=source_type
        )

    def queue_url_override(self, source_type: str) -> str:
        """Tip başına önceden enjekte edilmiş ana queue URL (boşsa get_queue_url ile çözülür)."""
        return {
            "rss": self.ORCH_SQS_QUEUE_RSS_URL,
            "email": self.ORCH_SQS_QUEUE_EMAIL_URL,
            "gov": self.ORCH_SQS_QUEUE_GOV_URL,
        }.get(source_type, "")


@lru_cache
def get_orchestrator_aws_settings() -> OrchestratorAwsSettings:
    return OrchestratorAwsSettings()


@dataclass(slots=True)
class InvokeResult:
    """Tek collector Lambda invoke sonucu — `CollectStageExecutor` sayaç/detail türetir."""

    ok: bool
    source_type: str
    status_code: int = 0
    request_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class CollectorInvoker(Protocol):
    """Collect aşaması invoke sözleşmesi (test mock'u bunu sağlar)."""

    async def invoke_collector(self, source_type: str) -> InvokeResult: ...


class LambdaInvoker:
    """Collector Lambda'larını senkron (`RequestResponse`) invoke eden boto3 sarmalayıcı.

    Senkron invoke ile collector'ın döndürdüğü sayaçlar (`published`/`sources_*`) beklenir;
    `ORCH_INVOKE_TIMEOUT_SECONDS` ile sonsuz bekleme önlenir → timeout `ok=False` üretir,
    aşama `partial`'a düşer (`Docs/04` §10.5 risk notu).
    """

    def __init__(
        self,
        *,
        settings: OrchestratorAwsSettings | None = None,
        lambda_client: BaseClient | None = None,
    ) -> None:
        self._settings = settings or get_orchestrator_aws_settings()
        self._client: BaseClient = lambda_client or boto3.client(
            "lambda", region_name=self._settings.AWS_REGION
        )

    async def invoke_collector(self, source_type: str) -> InvokeResult:
        function_name = self._settings.collector_function_name(source_type)
        body = json.dumps({"source_type": source_type}).encode("utf-8")

        def _call() -> dict[str, Any]:
            response: dict[str, Any] = self._client.invoke(
                FunctionName=function_name,
                InvocationType="RequestResponse",
                Payload=body,
            )
            return response

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(_call),
                timeout=self._settings.ORCH_INVOKE_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            logger.warning(
                "collector_invoke_timeout",
                extra={"source_type": source_type, "function_name": function_name},
            )
            return InvokeResult(
                ok=False, source_type=source_type, error="invoke timeout"
            )
        except (BotoCoreError, ClientError) as exc:
            logger.warning(
                "collector_invoke_error",
                extra={"source_type": source_type, "error": str(exc)},
            )
            return InvokeResult(ok=False, source_type=source_type, error=str(exc))

        return self._parse_invoke_response(source_type, response)

    @staticmethod
    def _parse_invoke_response(
        source_type: str, response: dict[str, Any]
    ) -> InvokeResult:
        status_code = int(response.get("StatusCode", 0))
        function_error = response.get("FunctionError")
        request_id = response.get("ResponseMetadata", {}).get("RequestId")

        raw_payload = response.get("Payload")
        if raw_payload is None:
            payload_bytes: Any = b""
        elif hasattr(raw_payload, "read"):
            payload_bytes = raw_payload.read()
        else:
            payload_bytes = raw_payload
        try:
            payload = json.loads(payload_bytes) if payload_bytes else {}
        except (json.JSONDecodeError, TypeError):
            payload = {}

        if function_error or not 200 <= status_code < 300:
            return InvokeResult(
                ok=False,
                source_type=source_type,
                status_code=status_code,
                request_id=request_id,
                error=function_error or f"invoke status {status_code}",
            )

        if not isinstance(payload, dict):
            payload = {}
        inner_status = int(payload.get("statusCode", status_code))
        inner_body = payload.get("body", {})
        if not 200 <= inner_status < 300:
            return InvokeResult(
                ok=False,
                source_type=source_type,
                status_code=status_code,
                request_id=request_id,
                error=f"handler status {inner_status}: {inner_body}",
            )

        return InvokeResult(
            ok=True,
            source_type=source_type,
            status_code=status_code,
            request_id=request_id,
            payload=inner_body if isinstance(inner_body, dict) else {},
        )


# --- İterasyon 4: SQS process gözlemi ---------------------------------------


@dataclass(slots=True)
class QueueDepth:
    """Tek SQS queue'nun anlık derinliği — `ProcessStageExecutor` drain kriterini türetir.

    `visible` görünür (`ApproximateNumberOfMessages`), `not_visible` uçuşta
    (`...NotVisible`, henüz silinmemiş işlenenler), `dlq` ölü-mektup derinliği. Drain =
    ana queue'da hiç mesaj kalmaması (görünür + uçuşta = 0); DLQ kalıcı başarısızlığı
    işaretler ve process'i sonsuz bekletmemek için ayrıca okunur (`Docs/04` §8).
    """

    source_type: str
    visible: int = 0
    not_visible: int = 0
    dlq: int = 0

    @property
    def in_flight(self) -> int:
        return self.visible + self.not_visible

    @property
    def is_drained(self) -> bool:
        return self.visible == 0 and self.not_visible == 0


class SqsObserver(Protocol):
    """Process aşaması queue gözlem sözleşmesi (test mock'u bunu sağlar)."""

    async def queue_depth(self, source_type: str) -> QueueDepth: ...


_VISIBLE_ATTR = "ApproximateNumberOfMessages"
_NOT_VISIBLE_ATTR = "ApproximateNumberOfMessagesNotVisible"


class BotoSqsObserver:
    """`sqs:GetQueueAttributes` ile ana queue + DLQ derinliğini okuyan boto3 sarmalayıcı.

    Yalnızca **okur** — mesaj almaz/silmez; processor iş mantığına dokunmaz (`Docs/10`
    §6.1 Don'ts). Queue URL önce env override'tan (`ORCH_SQS_QUEUE_*_URL`), yoksa
    `sqs:GetQueueUrl` ile addan çözülür ve cache'lenir. Çözülemeyen queue (örn. DLQ yoksa)
    derinliği 0 sayılır — gözlem run'ı düşürmez. Senkron boto3 çağrıları thread'e taşınır.
    """

    def __init__(
        self,
        *,
        settings: OrchestratorAwsSettings | None = None,
        sqs_client: BaseClient | None = None,
    ) -> None:
        self._settings = settings or get_orchestrator_aws_settings()
        self._client: BaseClient = sqs_client or boto3.client(
            "sqs", region_name=self._settings.AWS_REGION
        )
        self._url_cache: dict[str, str | None] = {}

    async def queue_depth(self, source_type: str) -> QueueDepth:
        main_url = await self._resolve_url(
            self._settings.queue_name_for_source_type(source_type),
            override=self._settings.queue_url_override(source_type),
        )
        dlq_url = await self._resolve_url(
            self._settings.dlq_name_for_source_type(source_type)
        )

        visible, not_visible = await self._read_depth(main_url) if main_url else (0, 0)
        dlq_visible, dlq_not_visible = (
            await self._read_depth(dlq_url) if dlq_url else (0, 0)
        )
        return QueueDepth(
            source_type=source_type,
            visible=visible,
            not_visible=not_visible,
            dlq=dlq_visible + dlq_not_visible,
        )

    async def _resolve_url(self, queue_name: str, *, override: str = "") -> str | None:
        if override:
            return override
        if queue_name in self._url_cache:
            return self._url_cache[queue_name]

        def _call() -> str:
            response: dict[str, Any] = self._client.get_queue_url(QueueName=queue_name)
            return str(response["QueueUrl"])

        try:
            url: str | None = await asyncio.to_thread(_call)
        except (BotoCoreError, ClientError) as exc:
            logger.warning(
                "sqs_queue_url_resolve_failed",
                extra={"queue_name": queue_name, "error": str(exc)},
            )
            url = None
        self._url_cache[queue_name] = url
        return url

    async def _read_depth(self, queue_url: str) -> tuple[int, int]:
        def _call() -> dict[str, Any]:
            response: dict[str, Any] = self._client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[_VISIBLE_ATTR, _NOT_VISIBLE_ATTR],
            )
            return response

        try:
            response = await asyncio.to_thread(_call)
        except (BotoCoreError, ClientError) as exc:
            logger.warning(
                "sqs_get_attributes_failed",
                extra={"queue_url": queue_url, "error": str(exc)},
            )
            return (0, 0)

        attrs = response.get("Attributes", {})
        return (
            int(attrs.get(_VISIBLE_ATTR, 0)),
            int(attrs.get(_NOT_VISIBLE_ATTR, 0)),
        )
