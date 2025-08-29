from aws_cdk import Stack, aws_ec2 as ec2, aws_sns as sns, Tags
from constructs import Construct
from constructs.secure_vpc import SecureVpc
from constructs.ecommerce_database import EcommerceDatabase
from constructs.ecommerce_compute import EcommerceCompute
from constructs.dr_orchestrator import DROrchestrator
from constructs.monitoring_dashboard import MonitoringDashboard
from config.environments import EnvironmentConfig


class DRRegionStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: EnvironmentConfig,
        primary_database,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # SNS Topic for DR notifications
        self.notification_topic = sns.Topic(
            self, "DRNotificationTopic", display_name="DR Region Notifications"
        )

        # Secure VPC (cost-optimized for pilot light)
        self.vpc_construct = SecureVpc(
            self, "DRVPC", cidr=config.dr_region.vpc_cidr, enable_flow_logs=True
        )
        self.vpc = self.vpc_construct.vpc

        # Security Groups (mirrored from primary)
        self.web_sg = ec2.SecurityGroup(
            self,
            "DRWebSG",
            vpc=self.vpc,
            description="DR Security group for web servers",
            allow_all_outbound=True,
        )
        self.web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))
        self.web_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443))

        self.alb_sg = ec2.SecurityGroup(
            self,
            "DRALBSG",
            vpc=self.vpc,
            description="DR Security group for ALB",
            allow_all_outbound=True,
        )
        self.alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(80))
        self.alb_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(443))

        self.db_sg = ec2.SecurityGroup(
            self,
            "DRDatabaseSG",
            vpc=self.vpc,
            description="DR Security group for database",
            allow_all_outbound=False,
        )
        self.db_sg.add_ingress_rule(self.web_sg, ec2.Port.tcp(3306))

        # Read Replica Database (Pilot Light component)
        self.database_construct = EcommerceDatabase(
            self,
            "DRDatabase",
            vpc=self.vpc,
            config=config.database,
            security_group=self.db_sg,
            notification_topic=self.notification_topic,
            is_primary=False,
            source_database=primary_database,
        )
        self.database = self.database_construct.database

        # Compute Infrastructure (Pilot Light - scaled to 0)
        self.compute_construct = EcommerceCompute(
            self,
            "DRCompute",
            vpc=self.vpc,
            config=config.compute,
            security_groups=[self.web_sg, self.alb_sg],
            notification_topic=self.notification_topic,
            is_pilot_light=True,  # This scales ASG to 0
        )
        self.load_balancer = self.compute_construct.load_balancer
        self.auto_scaling_group = self.compute_construct.auto_scaling_group

        # DR Orchestrator
        self.dr_orchestrator = DROrchestrator(
            self, "DROrchestrator", notification_topic=self.notification_topic
        )

        # Monitoring Dashboard
        self.monitoring = MonitoringDashboard(
            self,
            "Monitoring",
            primary_alb_arn="primary-alb-arn",  # Would be passed from primary stack
            dr_alb_arn=self.load_balancer.load_balancer_arn,
            primary_db_identifier="primary-db-id",  # Would be passed from primary stack
            dr_db_identifier=self.database.instance_identifier,
        )

        # Tags
        Tags.of(self).add("Environment", config.environment_name)
        Tags.of(self).add("Region", "DR")
        Tags.of(self).add("Application", "E-commerce")
        Tags.of(self).add("PilotLight", "True")
