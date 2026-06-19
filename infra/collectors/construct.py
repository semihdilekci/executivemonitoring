"""Collector EventBridge + Lambda orchestration CDK construct."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aws_cdk import Duration
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

_LAMBDA_STUB_DIR = Path(__file__).resolve().parent / "lambda_stub"


class CollectorOrchestration(Construct):
    """RSS/email/gov collector Lambda'ları ve EventBridge cron kuralları."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        lambda_role: Role,
        queues: dict[str, Queue],
    ) -> None:
        super().__init__(scope, construct_id)

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
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset(str(_LAMBDA_STUB_DIR)),
            role=lambda_role,
            memory_size=schedule.memory_mb,
            timeout=Duration.seconds(schedule.timeout_seconds),
            environment={
                "ENVIRONMENT": ENVIRONMENT,
                env_key: queue.queue_url,
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
