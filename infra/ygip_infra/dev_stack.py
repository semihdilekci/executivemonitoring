"""AWS dev environment stack — RDS, SQS+DLQ, S3, EventBridge, IAM."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_events as events,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_rds as rds,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_sqs as sqs,
)
from constructs import Construct

from ygip_infra.config import (
    AWS_REGION,
    COLLECTOR_QUEUE_TYPES,
    ENVIRONMENT,
    resource_name,
    sqs_dlq_name,
    sqs_queue_name,
)

if TYPE_CHECKING:
    from aws_cdk.aws_sqs import Queue


class YgipDevStack(Stack):
    """MVP-0 dev infrastructure (`dev-ygip-*` prefix)."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        Tags.of(self).add("project", "ygip")
        Tags.of(self).add("environment", ENVIRONMENT)

        vpc = self._create_vpc()
        archive_bucket = self._create_archive_bucket()
        queues = self._create_sqs_queues()
        database = self._create_database(vpc)
        self._create_eventbridge_placeholder()
        self._create_lambda_execution_role(archive_bucket, queues)

        CfnOutput(self, "VpcId", value=vpc.vpc_id, export_name="YgipDevVpcId")
        CfnOutput(
            self,
            "ArchiveBucketName",
            value=archive_bucket.bucket_name,
            export_name="YgipDevArchiveBucket",
        )
        CfnOutput(
            self,
            "RdsEndpoint",
            value=database.instance_endpoint.hostname,
            export_name="YgipDevRdsEndpoint",
        )
        CfnOutput(
            self,
            "RdsSecretArn",
            value=database.secret.secret_arn if database.secret else "",
            export_name="YgipDevRdsSecretArn",
        )
        for queue_type, queue in queues.items():
            CfnOutput(
                self,
                f"Sqs{queue_type.title()}Url",
                value=queue.queue_url,
                export_name=f"YgipDevSqs{queue_type.title()}Url",
            )

    def _create_vpc(self) -> ec2.Vpc:
        return ec2.Vpc(
            self,
            "Vpc",
            vpc_name=resource_name("vpc"),
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

    def _create_archive_bucket(self) -> s3.Bucket:
        return s3.Bucket(
            self,
            "Archive",
            bucket_name=f"{resource_name('archive')}-{self.account}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=False,
            removal_policy=RemovalPolicy.RETAIN,
        )

    def _create_sqs_queues(self) -> dict[str, Queue]:
        queues: dict[str, Queue] = {}
        for queue_type in COLLECTOR_QUEUE_TYPES:
            dlq = sqs.Queue(
                self,
                f"{queue_type.title()}Dlq",
                queue_name=sqs_dlq_name(queue_type),
                retention_period=Duration.days(14),
                encryption=sqs.QueueEncryption.SQS_MANAGED,
            )
            queue = sqs.Queue(
                self,
                f"{queue_type.title()}Queue",
                queue_name=sqs_queue_name(queue_type),
                visibility_timeout=Duration.minutes(5),
                retention_period=Duration.days(4),
                encryption=sqs.QueueEncryption.SQS_MANAGED,
                dead_letter_queue=sqs.DeadLetterQueue(
                    max_receive_count=3,
                    queue=dlq,
                ),
            )
            queues[queue_type] = queue
        return queues

    def _create_database(self, vpc: ec2.Vpc) -> rds.DatabaseInstance:
        security_group = ec2.SecurityGroup(
            self,
            "RdsSecurityGroup",
            vpc=vpc,
            security_group_name=resource_name("rds-sg"),
            description="YGIP dev RDS — VPC-internal PostgreSQL access only",
            allow_all_outbound=False,
        )
        security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="PostgreSQL from VPC",
        )

        parameter_group = rds.ParameterGroup(
            self,
            "PostgresParameterGroup",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16),
            description="YGIP dev PostgreSQL 16 parameters",
            parameters={
                "rds.force_ssl": "1",
            },
        )

        return rds.DatabaseInstance(
            self,
            "Database",
            instance_identifier=resource_name("rds"),
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_16),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            credentials=rds.Credentials.from_generated_secret(
                "ygip",
                secret_name="ygip/dev/database",
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[security_group],
            parameter_group=parameter_group,
            allocated_storage=20,
            storage_type=rds.StorageType.GP3,
            storage_encrypted=True,
            multi_az=False,
            publicly_accessible=False,
            backup_retention=Duration.days(0),
            deletion_protection=False,
            removal_policy=RemovalPolicy.SNAPSHOT,
            database_name="ygip_dev",
        )

    def _create_eventbridge_placeholder(self) -> events.Rule:
        return events.Rule(
            self,
            "CollectorSchedulePlaceholder",
            rule_name=resource_name("collector-schedule-placeholder"),
            description="Placeholder — collector cron rules added in Faz 2",
            schedule=events.Schedule.rate(Duration.days(1)),
            enabled=False,
        )

    def _create_lambda_execution_role(
        self,
        archive_bucket: s3.Bucket,
        queues: dict[str, Queue],
    ) -> iam.Role:
        account = self.account
        region = self.region or AWS_REGION

        role = iam.Role(
            self,
            "LambdaExecutionRole",
            role_name=resource_name("lambda-execution"),
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="YGIP dev Lambda execution — scoped to dev-ygip-* resources",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole",
                ),
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaVPCAccessExecutionRole",
                ),
            ],
        )

        queue_arns = [queue.queue_arn for queue in queues.values()]
        role.add_to_policy(
            iam.PolicyStatement(
                sid="SqsDevScoped",
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:SendMessage",
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:GetQueueUrl",
                    "sqs:ChangeMessageVisibility",
                ],
                resources=queue_arns,
            ),
        )

        role.add_to_policy(
            iam.PolicyStatement(
                sid="S3ArchiveDevScoped",
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                ],
                resources=[
                    archive_bucket.bucket_arn,
                    f"{archive_bucket.bucket_arn}/*",
                ],
            ),
        )

        role.add_to_policy(
            iam.PolicyStatement(
                sid="SecretsManagerDevScoped",
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
                resources=[f"arn:aws:secretsmanager:{region}:{account}:secret:ygip/dev/*"],
            ),
        )

        prod_deny_resources = [
            f"arn:aws:sqs:{region}:{account}:prod-ygip-*",
            f"arn:aws:sqs:{region}:{account}:ygip-prod-*",
            "arn:aws:s3:::prod-ygip-*",
            "arn:aws:s3:::prod-ygip-*/*",
            "arn:aws:s3:::ygip-prod-*",
            "arn:aws:s3:::ygip-prod-*/*",
            f"arn:aws:rds:{region}:{account}:db:prod-ygip-*",
            f"arn:aws:rds:{region}:{account}:db:ygip-prod-*",
            f"arn:aws:secretsmanager:{region}:{account}:secret:ygip/prod/*",
        ]
        role.add_to_policy(
            iam.PolicyStatement(
                sid="DenyProdResourceAccess",
                effect=iam.Effect.DENY,
                actions=["*"],
                resources=prod_deny_resources,
            ),
        )

        CfnOutput(
            self,
            "LambdaExecutionRoleArn",
            value=role.role_arn,
            export_name="YgipDevLambdaExecutionRoleArn",
        )

        return role
