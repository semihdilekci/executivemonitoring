"""Processor SQS-triggered Lambda orchestration CDK construct (`Docs/04` §8.0, §8.6–8.7)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from aws_cdk import Duration
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_logs as logs
from constructs import Construct
from ygip_infra.config import ENVIRONMENT, resource_name

if TYPE_CHECKING:
    from aws_cdk.aws_iam import Role
    from aws_cdk.aws_sqs import Queue

# Processor Lambda, collector'ların yazdığı kuyrukları tüketir (rss/email/gov);
# `api` kuyruğunun MVP-0'da collector'ı yok — trigger bağlanmaz (`Docs/10` §8.4).
PROCESSOR_SOURCE_TYPES: tuple[str, ...] = ("rss", "email", "gov")

# Embedding CPU-bound + LLM I/O — collector'dan yüksek profil (`Docs/10` §8.4).
_PROCESSOR_MEMORY_MB = 512
_PROCESSOR_TIMEOUT_SECONDS = 120
# Tek invoke'ta kaç SQS mesajı; queue visibility (5 dk) > Lambda timeout (2 dk).
_PROCESSOR_BATCH_SIZE = 10

# Bundle artifact (`scripts/build_lambda.sh processor` → dist/lambda/processor/);
# unified `services.processor.handlers.processor_handler.lambda_handler` giriş noktası.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUNDLE_DIR = _REPO_ROOT / "dist" / "lambda" / "processor"
# Bundle build edilmediğinde (CI synth) synth'in geçmesi için minimal placeholder.
_LAMBDA_STUB_DIR = Path(__file__).resolve().parent / "lambda_stub"

_PROCESSOR_HANDLER = "services.processor.handlers.processor_handler.lambda_handler"


def _resolve_processor_code() -> lambda_.Code:
    """Deploy'da bundle artifact'ı, yoksa (CI synth) stub placeholder'ı kullan.

    Gerçek deploy öncesi `./scripts/build_lambda.sh processor` zorunlu — aksi
    halde stub placeholder ile synth geçer ama runtime handler bulunamaz; stub
    batch'i tümüyle başarısız raporlar, mesaj 3 deneme sonrası DLQ'ya düşer
    (`infra/README.md` Lambda Bundle, `Docs/04` §8.7).
    """
    asset_dir = _BUNDLE_DIR if _BUNDLE_DIR.is_dir() else _LAMBDA_STUB_DIR
    return lambda_.Code.from_asset(str(asset_dir))


class ProcessorOrchestration(Construct):
    """rss/email/gov processor Lambda'ları ve SQS event source mapping'leri.

    Her kaynak tipi için ayrı `dev-ygip-processor-{type}` Lambda, ilgili ana
    kuyruğu (`dev-ygip-sqs-{type}`) partial batch failure ile tüketir. DLQ
    redrive policy kuyruk tanımında (`max_receive_count=3`) tutulur — burada
    yalnızca event source mapping bağlanır (`Docs/04` §8.6–8.7).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        lambda_role: Role,
        queues: dict[str, Queue],
        vpc: ec2.IVpc,
        security_group: ec2.ISecurityGroup,
    ) -> None:
        super().__init__(scope, construct_id)

        self._vpc = vpc
        self._security_group = security_group
        self.functions: dict[str, lambda_.Function] = {}

        for source_type in PROCESSOR_SOURCE_TYPES:
            queue = queues[source_type]
            fn = self._create_processor_function(source_type, lambda_role, queue)
            self.functions[source_type] = fn
            self._attach_sqs_trigger(fn, queue)

    def _create_processor_function(
        self,
        source_type: str,
        lambda_role: Role,
        queue: Queue,
    ) -> lambda_.Function:
        function_name = resource_name(f"processor-{source_type}")

        log_group = logs.LogGroup(
            self,
            f"{source_type.title()}LogGroup",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=logs.RetentionDays.TWO_WEEKS,
        )

        return lambda_.Function(
            self,
            f"{source_type.title()}Processor",
            function_name=function_name,
            description=f"YGIP {source_type} processor — SQS triggered pipeline",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler=_PROCESSOR_HANDLER,
            code=_resolve_processor_code(),
            role=lambda_role,
            memory_size=_PROCESSOR_MEMORY_MB,
            timeout=Duration.seconds(_PROCESSOR_TIMEOUT_SECONDS),
            # RDS/Redis VPC-internal — ingest + persist için VPC erişimi zorunlu
            # (`Docs/09` §7.3). Collector ile aynı SG + isolated subnet pattern.
            vpc=self._vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[self._security_group],
            environment={
                # AWS_REGION Lambda runtime tarafından otomatik sağlanır (reserved key).
                "ENVIRONMENT": ENVIRONMENT,
                f"SQS_QUEUE_{source_type.upper()}_URL": queue.queue_url,
                # Secret değil, deploy-time param (`Docs/09` §7); commit edilmez,
                # `cdk deploy` öncesi export edilir (`infra/README.md`).
                "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
                "REDIS_URL": os.environ.get("REDIS_URL", ""),
                # Boşsa embedding deterministic fallback'e düşer (`Docs/04` §8.5).
                "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
            },
            log_group=log_group,
        )

    def _attach_sqs_trigger(self, fn: lambda_.Function, queue: Queue) -> None:
        """SQS event source mapping — partial batch failure raporu açık.

        `report_batch_item_failures=True` → handler `batchItemFailures` döndürür;
        yalnızca başarısız mesajlar yeniden teslim edilir, kalanlar silinir.
        3. denemede başarısız mesaj kuyruğun DLQ'suna düşer (`Docs/04` §8.7).
        """
        fn.add_event_source(
            lambda_event_sources.SqsEventSource(
                queue,
                batch_size=_PROCESSOR_BATCH_SIZE,
                report_batch_item_failures=True,
            ),
        )
