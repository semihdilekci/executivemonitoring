"""Shared naming and environment constants for YGIP AWS resources."""

from __future__ import annotations

import os

import aws_cdk as cdk

AWS_REGION = "eu-west-1"
ENVIRONMENT = "dev"
RESOURCE_PREFIX = "dev-ygip"

COLLECTOR_QUEUE_TYPES = ("rss", "email", "gov", "api")

DEV_ENV = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION", AWS_REGION),
)


def resource_name(service: str) -> str:
    """Build a `{env}-ygip-{service}` resource name."""
    return f"{RESOURCE_PREFIX}-{service}"


def sqs_queue_name(queue_type: str) -> str:
    return resource_name(f"sqs-{queue_type}")


def sqs_dlq_name(queue_type: str) -> str:
    return resource_name(f"sqs-{queue_type}-dlq")
