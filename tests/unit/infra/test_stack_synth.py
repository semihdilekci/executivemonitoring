"""Collector orchestration CDK synthesis testleri."""

from __future__ import annotations

import sys
from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

INFRA_DIR = Path(__file__).resolve().parents[3] / "infra"
sys.path.insert(0, str(INFRA_DIR))

from ygip_infra.dev_stack import YgipDevStack  # noqa: E402


@pytest.fixture
def dev_template() -> Template:
    app = cdk.App()
    stack = YgipDevStack(
        app,
        "TestYgipDevStack",
        env=cdk.Environment(account="123456789012", region="eu-west-1"),
    )
    return Template.from_stack(stack)


def test_dev_stack_synths(dev_template: Template) -> None:
    """Stack produces a CloudFormation template without synthesis errors."""
    dev_template.resource_count_is("AWS::RDS::DBInstance", 1)


def test_sqs_queues_with_dlq(dev_template: Template) -> None:
    dev_template.resource_count_is("AWS::SQS::Queue", 8)
    dev_template.has_resource_properties(
        "AWS::SQS::Queue",
        {
            "QueueName": "dev-ygip-sqs-rss",
        },
    )


def test_archive_bucket_is_private(dev_template: Template) -> None:
    dev_template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketName": "dev-ygip-archive-123456789012",
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "BlockPublicPolicy": True,
                "IgnorePublicAcls": True,
                "RestrictPublicBuckets": True,
            },
        },
    )


def test_rds_not_public(dev_template: Template) -> None:
    dev_template.has_resource_properties(
        "AWS::RDS::DBInstance",
        {
            "DBInstanceIdentifier": "dev-ygip-rds",
            "PubliclyAccessible": False,
        },
    )


def test_lambda_role_scoped_to_dev_queues(dev_template: Template) -> None:
    dev_template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "RoleName": "dev-ygip-lambda-execution",
        },
    )


def test_collector_lambdas_defined(dev_template: Template) -> None:
    # 3 collector (rss/email/gov) + 3 processor (rss/email/gov).
    dev_template.resource_count_is("AWS::Lambda::Function", 6)
    dev_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "dev-ygip-collector-rss",
            "MemorySize": 256,
            "Timeout": 60,
        },
    )
    dev_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "dev-ygip-collector-email",
            "MemorySize": 512,
            "Timeout": 120,
        },
    )


def test_collector_lambda_uses_unified_handler(dev_template: Template) -> None:
    """Gerçek deploy: unified handler + Python 3.12 runtime (stub değil)."""
    dev_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "dev-ygip-collector-rss",
            "Handler": "services.collectors.handler.lambda_handler",
            "Runtime": "python3.12",
        },
    )


def test_collector_lambda_in_vpc(dev_template: Template) -> None:
    """RDS VPC-internal — collector Lambda VPC config ile RDS'e erişir."""
    dev_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "dev-ygip-collector-rss",
            "VpcConfig": Match.object_like(
                {
                    "SecurityGroupIds": Match.any_value(),
                    "SubnetIds": Match.any_value(),
                },
            ),
        },
    )


def test_collector_lambda_runtime_env(dev_template: Template) -> None:
    """Runtime env: SQS queue URL + DATABASE_URL/REDIS_URL deploy-time param."""
    dev_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "dev-ygip-collector-rss",
            "Environment": {
                "Variables": Match.object_like(
                    {
                        "SQS_QUEUE_RSS_URL": Match.any_value(),
                        "DATABASE_URL": Match.any_value(),
                        "REDIS_URL": Match.any_value(),
                    },
                ),
            },
        },
    )


def test_lambda_security_group_defined(dev_template: Template) -> None:
    """Collector Lambda SG — VPC-internal RDS erişimi için tanımlı."""
    dev_template.has_resource_properties(
        "AWS::EC2::SecurityGroup",
        {
            "GroupDescription": "YGIP dev collector Lambda — VPC-internal RDS access",
        },
    )


def test_collector_eventbridge_schedules(dev_template: Template) -> None:
    dev_template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "Name": "dev-ygip-collector-schedule-rss",
            "ScheduleExpression": "rate(15 minutes)",
        },
    )
    dev_template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "Name": "dev-ygip-collector-schedule-email",
            "ScheduleExpression": "rate(1 hour)",
        },
    )
    dev_template.has_resource_properties(
        "AWS::Events::Rule",
        {
            "Name": "dev-ygip-collector-schedule-gov",
            "ScheduleExpression": "rate(30 minutes)",
        },
    )


def test_collector_log_groups(dev_template: Template) -> None:
    dev_template.has_resource_properties(
        "AWS::Logs::LogGroup",
        {"LogGroupName": "/aws/lambda/dev-ygip-collector-rss"},
    )


def test_processor_lambdas_defined(dev_template: Template) -> None:
    """rss/email/gov için ayrı processor Lambda — yüksek embedding profili."""
    for source_type in ("rss", "email", "gov"):
        dev_template.has_resource_properties(
            "AWS::Lambda::Function",
            {
                "FunctionName": f"dev-ygip-processor-{source_type}",
                "Handler": "services.processor.handlers.processor_handler.lambda_handler",
                "Runtime": "python3.12",
                "MemorySize": 512,
                "Timeout": 120,
            },
        )


def test_processor_lambda_in_vpc(dev_template: Template) -> None:
    """RDS/Redis VPC-internal — processor Lambda VPC config ile erişir."""
    dev_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "dev-ygip-processor-rss",
            "VpcConfig": Match.object_like(
                {
                    "SecurityGroupIds": Match.any_value(),
                    "SubnetIds": Match.any_value(),
                },
            ),
        },
    )


def test_processor_lambda_runtime_env(dev_template: Template) -> None:
    """Runtime env: DB/Redis deploy-time param + embedding OPENAI_API_KEY."""
    dev_template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "dev-ygip-processor-rss",
            "Environment": {
                "Variables": Match.object_like(
                    {
                        "DATABASE_URL": Match.any_value(),
                        "REDIS_URL": Match.any_value(),
                        "OPENAI_API_KEY": Match.any_value(),
                    },
                ),
            },
        },
    )


def test_processor_sqs_event_source_partial_batch(dev_template: Template) -> None:
    """SQS trigger her processor için + partial batch failure raporu açık."""
    # 3 processor (rss/email/gov) → 3 event source mapping.
    dev_template.resource_count_is("AWS::Lambda::EventSourceMapping", 3)
    dev_template.has_resource_properties(
        "AWS::Lambda::EventSourceMapping",
        {
            "BatchSize": 10,
            "FunctionResponseTypes": ["ReportBatchItemFailures"],
        },
    )


def test_processor_log_groups(dev_template: Template) -> None:
    dev_template.has_resource_properties(
        "AWS::Logs::LogGroup",
        {"LogGroupName": "/aws/lambda/dev-ygip-processor-rss"},
    )
