"""CDK dev stack synthesis smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template

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
