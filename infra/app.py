#!/usr/bin/env python3
"""CDK application entry point for YGIP dev infrastructure."""

import aws_cdk as cdk
from ygip_infra.config import DEV_ENV
from ygip_infra.dev_stack import YgipDevStack

app = cdk.App()

YgipDevStack(
    app,
    "YgipDevStack",
    env=DEV_ENV,
    description="YGIP MVP-0 dev environment (RDS, SQS, S3, EventBridge, IAM)",
)

app.synth()
