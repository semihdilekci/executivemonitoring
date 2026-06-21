"""Collector EventBridge + Lambda orchestration CDK construct."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from aws_cdk import Duration
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct
from ygip_infra.config import ENVIRONMENT, resource_name

from collectors.schedules import COLLECTOR_SCHEDULES, CollectorScheduleConfig

if TYPE_CHECKING:
    from aws_cdk.aws_iam import Role
    from aws_cdk.aws_sqs import Queue

# Bundle artifact (`scripts/build_lambda.sh collector` → dist/lambda/collector/);
# unified `services.collectors.handler.lambda_handler` giriş noktası içerir.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_BUNDLE_DIR = _REPO_ROOT / "dist" / "lambda" / "collector"
# Bundle build edilmediğinde (CI synth) synth'in geçmesi için minimal placeholder.
_LAMBDA_STUB_DIR = Path(__file__).resolve().parent / "lambda_stub"

_COLLECTOR_HANDLER = "services.collectors.handler.lambda_handler"


def _resolve_collector_code() -> lambda_.Code:
    """Deploy'da bundle artifact'ı, yoksa (CI synth) stub placeholder'ı kullan.

    Gerçek deploy öncesi `./scripts/build_lambda.sh collector` zorunlu — aksi
    halde stub placeholder ile synth geçer ama runtime handler bulunamaz
    (`infra/README.md` Lambda Bundle).
    """
    asset_dir = _BUNDLE_DIR if _BUNDLE_DIR.is_dir() else _LAMBDA_STUB_DIR
    return lambda_.Code.from_asset(str(asset_dir))


class CollectorOrchestration(Construct):
    """RSS/email/gov collector Lambda'ları ve EventBridge cron kuralları."""

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

        for schedule in COLLECTOR_SCHEDULES:
            fn = self._create_collector_function(schedule, lambda_role, queues)
            self.functions[schedule.source_type] = fn
            self._create_schedule_rule(schedule, fn)

    def _create_collector_function(
        self,
        schedule: CollectorScheduleConfig,
        lambda_role: Role,
        queues: dict[str, Queue],
    ) -> lambda_.Function:
        source_type = schedule.source_type
        function_name = resource_name(f"collector-{source_type}")

        log_group = logs.LogGroup(
            self,
            f"{source_type.title()}LogGroup",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=logs.RetentionDays.TWO_WEEKS,
        )

        queue = queues[source_type]
        env_key = f"SQS_QUEUE_{source_type.upper()}_URL"

        return lambda_.Function(
            self,
            f"{source_type.title()}Collector",
            function_name=function_name,
            description=f"YGIP {source_type} collector — EventBridge scheduled",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler=_COLLECTOR_HANDLER,
            code=_resolve_collector_code(),
            role=lambda_role,
            memory_size=schedule.memory_mb,
            timeout=Duration.seconds(schedule.timeout_seconds),
            # RDS VPC-internal — collector `load_active_sources` için VPC erişimi
            # zorunlu (`Docs/09` §7.3). RDS SG, VPC CIDR'den 5432 ingress'e izin verir.
            vpc=self._vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[self._security_group],
            environment={
                # AWS_REGION Lambda runtime tarafından otomatik sağlanır (reserved key).
                "ENVIRONMENT": ENVIRONMENT,
                env_key: queue.queue_url,
                # Secret değil, deploy-time param (`Docs/09` §7); commit edilmez,
                # `cdk deploy` öncesi export edilir (`infra/README.md`).
                "DATABASE_URL": os.environ.get("DATABASE_URL", ""),
                "REDIS_URL": os.environ.get("REDIS_URL", ""),
            },
            log_group=log_group,
        )

    def _create_schedule_rule(
        self,
        schedule: CollectorScheduleConfig,
        fn: lambda_.Function,
    ) -> events.Rule:
        source_type = schedule.source_type
        return events.Rule(
            self,
            f"{source_type.title()}Schedule",
            rule_name=resource_name(f"collector-schedule-{source_type}"),
            description=(
                f"YGIP {source_type} collector — her {schedule.rate_minutes} dakikada bir"
            ),
            schedule=events.Schedule.rate(Duration.minutes(schedule.rate_minutes)),
            targets=[
                targets.LambdaFunction(
                    fn,
                    event=events.RuleTargetInput.from_object({"source_type": source_type}),
                ),
            ],
        )
