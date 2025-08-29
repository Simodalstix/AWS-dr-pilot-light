from aws_cdk import (
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    Duration,
)
from constructs import Construct


class GlobalDNS(Construct):
    """
    Route 53 global DNS with health checks and failover routing
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        domain_name: str,
        primary_alb_dns: str,
        dr_alb_dns: str,
        notification_topic: sns.Topic,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Hosted Zone
        self.hosted_zone = route53.HostedZone(self, "HostedZone", zone_name=domain_name)

        # Health Checks
        self.primary_health_check = route53.CfnHealthCheck(
            self,
            "PrimaryHealthCheck",
            type="HTTPS",
            resource_path="/health",
            fully_qualified_domain_name=primary_alb_dns,
            request_interval=30,
            failure_threshold=3,
        )

        self.dr_health_check = route53.CfnHealthCheck(
            self,
            "DRHealthCheck",
            type="HTTPS",
            resource_path="/health",
            fully_qualified_domain_name=dr_alb_dns,
            request_interval=30,
            failure_threshold=3,
        )

        # DNS Records with Failover
        self.primary_record = route53.ARecord(
            self,
            "PrimaryRecord",
            zone=self.hosted_zone,
            record_name="app",
            target=route53.RecordTarget.from_alias(targets.LoadBalancerTarget(primary_alb_dns)),
            set_identifier="Primary",
            failover=route53.FailoverPolicy.PRIMARY,
            health_check_id=self.primary_health_check.attr_health_check_id,
        )

        self.dr_record = route53.ARecord(
            self,
            "DRRecord",
            zone=self.hosted_zone,
            record_name="app",
            target=route53.RecordTarget.from_alias(targets.LoadBalancerTarget(dr_alb_dns)),
            set_identifier="DR",
            failover=route53.FailoverPolicy.SECONDARY,
            health_check_id=self.dr_health_check.attr_health_check_id,
        )

        # CloudWatch Alarms for health checks
        self._create_health_check_alarms(notification_topic)

    def _create_health_check_alarms(self, notification_topic: sns.Topic):
        """Create alarms for Route 53 health check failures"""

        primary_alarm = cloudwatch.Alarm(
            self,
            "PrimaryHealthAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/Route53",
                metric_name="HealthCheckStatus",
                dimensions_map={"HealthCheckId": self.primary_health_check.attr_health_check_id},
            ),
            threshold=1,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            alarm_description="Primary region health check failed",
        )

        primary_alarm.add_alarm_action(cloudwatch.SnsAction(notification_topic))
