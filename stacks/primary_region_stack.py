from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_elasticloadbalancingv2 as elbv2,
    aws_autoscaling as autoscaling,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
    RemovalPolicy,
    Duration
)
from constructs import Construct

class PrimaryRegionStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # VPC
        self.vpc = ec2.Vpc(self, "PrimaryVPC",
            max_azs=2,
            nat_gateways=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
                ec2.SubnetConfiguration(name="Database", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24)
            ]
        )

        # Security Groups
        web_sg = ec2.SecurityGroup(self, "WebSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=True
        )
        web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))
        web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443))

        db_sg = ec2.SecurityGroup(self, "DatabaseSecurityGroup",
            vpc=self.vpc,
            allow_all_outbound=False
        )
        db_sg.add_ingress_rule(web_sg, ec2.Port.tcp(3306))

        # RDS Database
        self.database = rds.DatabaseInstance(self, "PrimaryDatabase",
            engine=rds.DatabaseInstanceEngine.mysql(version=rds.MysqlEngineVersion.VER_8_0),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[db_sg],
            database_name="appdb",
            backup_retention=Duration.days(7),
            deletion_protection=False,
            removal_policy=RemovalPolicy.DESTROY
        )

        # S3 Bucket for application data
        self.app_bucket = s3.Bucket(self, "AppDataBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Launch Template
        launch_template = ec2.LaunchTemplate(self, "WebServerTemplate",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machine_image=ec2.AmazonLinuxImage(generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2),
            security_group=web_sg,
            user_data=ec2.UserData.for_linux()
        )

        # Auto Scaling Group
        self.asg = autoscaling.AutoScalingGroup(self, "WebServerASG",
            vpc=self.vpc,
            launch_template=launch_template,
            min_capacity=2,
            max_capacity=10,
            desired_capacity=2,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)
        )

        # Application Load Balancer
        self.load_balancer = elbv2.ApplicationLoadBalancer(self, "PrimaryALB",
            vpc=self.vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC)
        )

        listener = self.load_balancer.add_listener("Listener",
            port=80,
            default_targets=[self.asg]
        )