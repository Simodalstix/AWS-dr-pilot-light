from aws_cdk import aws_cloudwatch as cloudwatch, aws_logs as logs, RemovalPolicy
from constructs import Construct
from typing import List


class MonitoringDashboard(Construct):
    """
    Comprehensive CloudWatch dashboard for DR monitoring
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        primary_alb_arn: str,
        dr_alb_arn: str,
        primary_db_identifier: str,
        dr_db_identifier: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Log Groups
        self.dr_log_group = logs.LogGroup(
            self,
            "DRLogGroup",
            log_group_name="/aws/dr/pilot-light",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Custom Metrics
        self.rto_metric = cloudwatch.Metric(
            namespace="DR/PilotLight",
            metric_name="RecoveryTimeObjective",
            unit=cloudwatch.Unit.SECONDS,
        )

        self.rpo_metric = cloudwatch.Metric(
            namespace="DR/PilotLight",
            metric_name="RecoveryPointObjective",
            unit=cloudwatch.Unit.SECONDS,
        )

        # Dashboard
        self.dashboard = cloudwatch.Dashboard(
            self, "DRDashboard", dashboard_name="DR-PilotLight-Monitoring"
        )

        # Add widgets
        self._add_infrastructure_widgets(primary_alb_arn, dr_alb_arn)
        self._add_database_widgets(primary_db_identifier, dr_db_identifier)
        self._add_dr_metrics_widgets()

    def _add_infrastructure_widgets(self, primary_alb_arn: str, dr_alb_arn: str):
        """Add infrastructure monitoring widgets"""

        # ALB Request Count
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="ALB Request Count",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/ApplicationELB",
                        metric_name="RequestCount",
                        dimensions_map={"LoadBalancer": primary_alb_arn.split("/")[-1]},
                        label="Primary Region",
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/ApplicationELB",
                        metric_name="RequestCount",
                        dimensions_map={"LoadBalancer": dr_alb_arn.split("/")[-1]},
                        label="DR Region",
                    ),
                ],
                width=12,
                height=6,
            )
        )

        # ALB Response Time
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="ALB Response Time",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/ApplicationELB",
                        metric_name="TargetResponseTime",
                        dimensions_map={"LoadBalancer": primary_alb_arn.split("/")[-1]},
                        label="Primary Region",
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/ApplicationELB",
                        metric_name="TargetResponseTime",
                        dimensions_map={"LoadBalancer": dr_alb_arn.split("/")[-1]},
                        label="DR Region",
                    ),
                ],
                width=12,
                height=6,
            )
        )

    def _add_database_widgets(self, primary_db_id: str, dr_db_id: str):
        """Add database monitoring widgets"""

        # Database CPU
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Database CPU Utilization",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/RDS",
                        metric_name="CPUUtilization",
                        dimensions_map={"DBInstanceIdentifier": primary_db_id},
                        label="Primary DB",
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/RDS",
                        metric_name="CPUUtilization",
                        dimensions_map={"DBInstanceIdentifier": dr_db_id},
                        label="DR DB (Read Replica)",
                    ),
                ],
                width=12,
                height=6,
            )
        )

        # Database Connections
        self.dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Database Connections",
                left=[
                    cloudwatch.Metric(
                        namespace="AWS/RDS",
                        metric_name="DatabaseConnections",
                        dimensions_map={"DBInstanceIdentifier": primary_db_id},
                        label="Primary DB",
                    ),
                    cloudwatch.Metric(
                        namespace="AWS/RDS",
                        metric_name="DatabaseConnections",
                        dimensions_map={"DBInstanceIdentifier": dr_db_id},
                        label="DR DB",
                    ),
                ],
                width=12,
                height=6,
            )
        )

    def _add_dr_metrics_widgets(self):
        """Add DR-specific metrics widgets"""

        # RTO/RPO Metrics
        self.dashboard.add_widgets(
            cloudwatch.SingleValueWidget(
                title="Recovery Objectives",
                metrics=[self.rto_metric, self.rpo_metric],
                width=6,
                height=6,
            )
        )

        # DR Status
        self.dashboard.add_widgets(
            cloudwatch.LogQueryWidget(
                title="DR Events",
                log_group=self.dr_log_group,
                query_lines=[
                    "fields @timestamp, @message",
                    "filter @message like /DR/",
                    "sort @timestamp desc",
                    "limit 20",
                ],
                width=18,
                height=6,
            )
        )
