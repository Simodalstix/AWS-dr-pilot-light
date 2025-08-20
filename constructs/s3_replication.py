from aws_cdk import (
    aws_s3 as s3,
    aws_iam as iam,
    aws_kms as kms,
    RemovalPolicy,
    Duration
)
from constructs import Construct

class S3Replication(Construct):
    """
    S3 cross-region replication for application data
    """
    
    def __init__(self, scope: Construct, construct_id: str,
                 source_region: str,
                 destination_region: str,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # KMS Keys for encryption
        self.source_key = kms.Key(self, "SourceKey",
            description="KMS key for source S3 bucket",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        self.destination_key = kms.Key(self, "DestinationKey", 
            description="KMS key for destination S3 bucket",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Source Bucket (Primary Region)
        self.source_bucket = s3.Bucket(self, "SourceBucket",
            versioned=True,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.source_key,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="TransitionToIA",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ]
        )
        
        # Destination Bucket (DR Region)
        self.destination_bucket = s3.Bucket(self, "DestinationBucket",
            versioned=True,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=self.destination_key,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
        
        # Replication Role
        self.replication_role = iam.Role(self, "ReplicationRole",
            assumed_by=iam.ServicePrincipal("s3.amazonaws.com"),
            inline_policies={
                "ReplicationPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "s3:GetObjectVersionForReplication",
                                "s3:GetObjectVersionAcl"
                            ],
                            resources=[f"{self.source_bucket.bucket_arn}/*"]
                        ),
                        iam.PolicyStatement(
                            actions=["s3:ListBucket"],
                            resources=[self.source_bucket.bucket_arn]
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "s3:ReplicateObject",
                                "s3:ReplicateDelete"
                            ],
                            resources=[f"{self.destination_bucket.bucket_arn}/*"]
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "kms:Decrypt",
                                "kms:GenerateDataKey"
                            ],
                            resources=[
                                self.source_key.key_arn,
                                self.destination_key.key_arn
                            ]
                        )
                    ]
                )
            }
        )
        
        # Replication Configuration
        replication_config = s3.CfnBucket.ReplicationConfigurationProperty(
            role=self.replication_role.role_arn,
            rules=[
                s3.CfnBucket.ReplicationRuleProperty(
                    id="ReplicateAll",
                    status="Enabled",
                    prefix="",
                    destination=s3.CfnBucket.ReplicationDestinationProperty(
                        bucket=self.destination_bucket.bucket_arn,
                        storage_class="STANDARD_IA",
                        encryption_configuration=s3.CfnBucket.EncryptionConfigurationProperty(
                            replica_kms_key_id=self.destination_key.key_arn
                        )
                    )
                )
            ]
        )
        
        # Apply replication to source bucket
        cfn_source_bucket = self.source_bucket.node.default_child
        cfn_source_bucket.replication_configuration = replication_config