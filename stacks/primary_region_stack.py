from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_sns as sns,
    Tags
)
from constructs import Construct
from constructs.secure_vpc import SecureVpc
from constructs.ecommerce_database import EcommerceDatabase
from constructs.ecommerce_compute import EcommerceCompute
from constructs.security_stack import SecurityStack
from constructs.s3_replication import S3Replication
from config.environments import EnvironmentConfig

class PrimaryRegionStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, 
                 config: EnvironmentConfig,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # SNS Topic for notifications
        self.notification_topic = sns.Topic(self, "NotificationTopic",
            display_name="E-commerce DR Notifications"
        )
        
        # Secure VPC
        self.vpc_construct = SecureVpc(self, "VPC",
            cidr=config.primary_region.vpc_cidr,
            enable_flow_logs=True
        )
        self.vpc = self.vpc_construct.vpc
        
        # Security Groups
        self.web_sg = ec2.SecurityGroup(self, "WebSG",
            vpc=self.vpc,
            description="Security group for web servers",
            allow_all_outbound=True
        )
        self.web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))
        self.web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443))
        
        self.alb_sg = ec2.SecurityGroup(self, "ALBSG",
            vpc=self.vpc,
            description="Security group for ALB",
            allow_all_outbound=True
        )
        self.alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))
        self.alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443))
        
        self.db_sg = ec2.SecurityGroup(self, "DatabaseSG",
            vpc=self.vpc,
            description="Security group for database",
            allow_all_outbound=False
        )
        self.db_sg.add_ingress_rule(self.web_sg, ec2.Port.tcp(3306))
        
        # Database
        self.database_construct = EcommerceDatabase(self, "Database",
            vpc=self.vpc,
            config=config.database,
            security_group=self.db_sg,
            notification_topic=self.notification_topic,
            is_primary=True
        )
        self.database = self.database_construct.database
        
        # Compute Infrastructure
        self.compute_construct = EcommerceCompute(self, "Compute",
            vpc=self.vpc,
            config=config.compute,
            security_groups=[self.web_sg, self.alb_sg],
            notification_topic=self.notification_topic,
            is_pilot_light=False
        )
        self.load_balancer = self.compute_construct.load_balancer
        self.auto_scaling_group = self.compute_construct.auto_scaling_group
        
        # S3 Replication
        self.s3_replication = S3Replication(self, "S3Replication",
            source_region=config.primary_region.region,
            destination_region=config.dr_region.region
        )
        
        # Security Stack
        self.security = SecurityStack(self, "Security",
            notification_topic=self.notification_topic
        )
        
        # Tags
        Tags.of(self).add("Environment", config.environment_name)
        Tags.of(self).add("Region", "Primary")
        Tags.of(self).add("Application", "E-commerce")