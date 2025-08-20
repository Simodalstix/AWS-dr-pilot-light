from aws_cdk import (
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    aws_kms as kms,
    aws_logs as logs,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    RemovalPolicy,
    Duration,
    Tags
)
from constructs import Construct
from config.environments import DatabaseConfig
from typing import Optional

class EcommerceDatabase(Construct):
    """
    Production-grade RDS MySQL cluster for e-commerce platform
    Includes encryption, monitoring, automated backups, and read replicas
    """
    
    def __init__(self, scope: Construct, construct_id: str,
                 vpc: ec2.Vpc,
                 config: DatabaseConfig,
                 security_group: ec2.SecurityGroup,
                 notification_topic: sns.Topic,
                 is_primary: bool = True,
                 source_database: Optional[rds.DatabaseInstance] = None,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.config = config
        self.vpc = vpc
        
        # KMS key for database encryption
        self.db_key = kms.Key(self, "DatabaseKey",
            description="KMS key for RDS encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Database credentials in Secrets Manager
        if is_primary:
            self.db_secret = secretsmanager.Secret(self, "DatabaseSecret",
                description="E-commerce database credentials",
                generate_secret_string=secretsmanager.SecretStringGenerator(
                    secret_string_template='{"username": "ecomadmin"}',
                    generate_string_key="password",
                    exclude_characters=" %+~`#$&*()|[]{}:;<>?!'/\"\\",
                    password_length=32
                ),
                kms_key=self.db_key
            )
        
        # Parameter Group for performance optimization
        self.parameter_group = rds.ParameterGroup(self, "DatabaseParameterGroup",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.of(config.engine_version)
            ),
            parameters={
                "innodb_buffer_pool_size": "{DBInstanceClassMemory*3/4}",
                "max_connections": "1000",
                "slow_query_log": "1",
                "long_query_time": "2",
                "log_queries_not_using_indexes": "1"
            }
        )
        
        # Option Group for enhanced monitoring
        self.option_group = rds.OptionGroup(self, "DatabaseOptionGroup",
            engine=rds.DatabaseInstanceEngine.mysql(
                version=rds.MysqlEngineVersion.of(config.engine_version)
            ),
            configurations=[]
        )
        
        # Subnet Group
        self.subnet_group = rds.SubnetGroup(self, "DatabaseSubnetGroup",
            description="Subnet group for e-commerce database",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            )
        )
        
        if is_primary:
            # Primary Database Instance
            self.database = rds.DatabaseInstance(self, "PrimaryDatabase",
                engine=rds.DatabaseInstanceEngine.mysql(
                    version=rds.MysqlEngineVersion.of(config.engine_version)
                ),
                instance_type=ec2.InstanceType(config.instance_class),
                vpc=vpc,
                subnet_group=self.subnet_group,
                security_groups=[security_group],
                credentials=rds.Credentials.from_secret(self.db_secret),
                database_name="ecommerce",
                parameter_group=self.parameter_group,
                option_group=self.option_group,
                backup_retention=Duration.days(config.backup_retention_days),
                backup_window="03:00-04:00",
                maintenance_window="sun:04:00-sun:05:00",
                multi_az=config.multi_az,
                storage_encrypted=config.encrypted,
                storage_encryption_key=self.db_key,
                monitoring_interval=Duration.seconds(60),
                enable_performance_insights=True,
                performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
                cloudwatch_logs_exports=["error", "general", "slow-query"],
                deletion_protection=True,
                delete_automated_backups=False,
                removal_policy=RemovalPolicy.SNAPSHOT
            )
        else:
            # Read Replica for DR
            self.database = rds.DatabaseInstanceReadReplica(self, "ReadReplica",
                source_database_instance=source_database,
                instance_type=ec2.InstanceType(config.instance_class),
                vpc=vpc,
                subnet_group=self.subnet_group,
                security_groups=[security_group],
                parameter_group=self.parameter_group,
                option_group=self.option_group,
                multi_az=config.multi_az,
                monitoring_interval=Duration.seconds(60),
                enable_performance_insights=True,
                performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
                deletion_protection=False,
                remove_source_database_on_read_replica_deletion=False,
                removal_policy=RemovalPolicy.DESTROY
            )
        
        # CloudWatch Alarms
        self._create_database_alarms(notification_topic)
        
        # Tags
        Tags.of(self).add("Component", "Database")
        Tags.of(self).add("Application", "E-commerce")
        Tags.of(self).add("Backup", "Automated")
    
    def _create_database_alarms(self, notification_topic: sns.Topic):
        """Create comprehensive CloudWatch alarms for database monitoring"""
        
        # CPU Utilization
        cloudwatch.Alarm(self, "DatabaseCPUAlarm",
            metric=self.database.metric_cpu_utilization(),
            threshold=80,
            evaluation_periods=2,
            alarm_description="Database CPU utilization is high"
        ).add_alarm_action(
            cloudwatch.SnsAction(notification_topic)
        )
        
        # Database Connections
        cloudwatch.Alarm(self, "DatabaseConnectionsAlarm",
            metric=self.database.metric_database_connections(),
            threshold=800,
            evaluation_periods=2,
            alarm_description="Database connection count is high"
        ).add_alarm_action(
            cloudwatch.SnsAction(notification_topic)
        )
        
        # Read Latency
        cloudwatch.Alarm(self, "DatabaseReadLatencyAlarm",
            metric=self.database.metric_read_latency(),
            threshold=0.2,
            evaluation_periods=2,
            alarm_description="Database read latency is high"
        ).add_alarm_action(
            cloudwatch.SnsAction(notification_topic)
        )
        
        # Write Latency
        cloudwatch.Alarm(self, "DatabaseWriteLatencyAlarm",
            metric=self.database.metric_write_latency(),
            threshold=0.2,
            evaluation_periods=2,
            alarm_description="Database write latency is high"
        ).add_alarm_action(
            cloudwatch.SnsAction(notification_topic)
        )