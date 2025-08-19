from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_elasticloadbalancingv2 as elbv2,
    aws_autoscaling as autoscaling,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    RemovalPolicy,
    Duration
)
from constructs import Construct

class DRRegionStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, primary_vpc_id: str, primary_db_instance, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC (mirrored from primary)
        self.vpc = ec2.Vpc(self, "DRVPC",
            max_azs=2,
            nat_gateways=1,  # Minimal for cost optimization
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
                ec2.SubnetConfiguration(name="Database", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24)
            ]
        )

        # Security Groups (mirrored from primary)
        web_sg = ec2.SecurityGroup(self, "DRWebSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True
        )
        web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))
        web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443))

        db_sg = ec2.SecurityGroup(self, "DRDatabaseSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=False
        )
        db_sg.add_ingress_rule(web_sg, ec2.Port.tcp(3306))

        # RDS Read Replica (Pilot Light component)
        self.read_replica = rds.DatabaseInstanceReadReplica(self, "DRReadReplica",
            source_database_instance=primary_db_instance,
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[db_sg],
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY
        )

        # S3 Bucket for DR (with cross-region replication configured separately)
        self.dr_bucket = s3.Bucket(self, "DRAppDataBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Pre-configured Launch Template (ready but not active)
        launch_template = ec2.LaunchTemplate(self, "DRWebServerTemplate",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machine_image=ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
            security_group=web_sg,
            user_data=ec2.UserData.for_linux()
        )

        # Auto Scaling Group (initially with 0 capacity - Pilot Light)
        self.asg = autoscaling.AutoScalingGroup(self, "DRWebServerASG",
            vpc=self.vpc,
            launch_template=launch_template,
            min_capacity=0,  # Pilot Light: no running instances
            max_capacity=10,
            desired_capacity=0,  # Pilot Light: no running instances
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )

        # Application Load Balancer (pre-configured but minimal)
        self.load_balancer = elbv2.ApplicationLoadBalancer(self, "DRALB",
            vpc=self.vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )

        listener = self.load_balancer.add_listener("DRListener",
            port=80,
            default_targets=[self.asg]
        )

        # Lambda function for DR activation
        dr_activation_role = iam.Role(self, "DRActivationRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "DRActivationPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "autoscaling:UpdateAutoScalingGroup",
                                "rds:PromoteReadReplica",
                                "route53:ChangeResourceRecordSets"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )

        self.dr_activation_function = lambda_.Function(self, "DRActivationFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            role=dr_activation_role,
            code=lambda_.Code.from_inline("""
import boto3
import json

def handler(event, context):
    autoscaling = boto3.client('autoscaling')
    rds = boto3.client('rds')
    
    # Scale up ASG
    autoscaling.update_auto_scaling_group(
        AutoScalingGroupName=event['asg_name'],
        DesiredCapacity=2,
        MinSize=2
    )
    
    # Promote read replica
    rds.promote_read_replica(
        DBInstanceIdentifier=event['replica_id']
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps('DR activation initiated')
    }
            """),
            timeout=Duration.minutes(5)
        )