from aws_cdk import (
    Stack,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as event_targets,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    Duration
)
from constructs import Construct

class GlobalResourcesStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, primary_alb_dns: str, dr_alb_dns: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # SNS Topic for DR notifications
        self.dr_notification_topic = sns.Topic(self, "DRNotificationTopic",
            display_name="DR Activation Notifications"
        )

        # Route 53 Hosted Zone (replace with your domain)
        self.hosted_zone = route53.HostedZone(self, "AppHostedZone",
            zone_name="example.com"  # Replace with your domain
        )

        # Health Check for Primary Region
        self.primary_health_check = route53.CfnHealthCheck(self, "PrimaryHealthCheck",
            type="HTTPS",
            resource_path="/health",
            fully_qualified_domain_name=primary_alb_dns,
            request_interval=30,
            failure_threshold=3
        )

        # Primary DNS Record (Active)
        self.primary_record = route53.ARecord(self, "PrimaryRecord",
            zone=self.hosted_zone,
            record_name="app",
            target=route53.RecordTarget.from_alias(
                targets.LoadBalancerTarget(primary_alb_dns)
            ),
            set_identifier="Primary",
            failover=route53.FailoverPolicy.PRIMARY,
            health_check_id=self.primary_health_check.attr_health_check_id
        )

        # DR DNS Record (Standby)
        self.dr_record = route53.ARecord(self, "DRRecord",
            zone=self.hosted_zone,
            record_name="app",
            target=route53.RecordTarget.from_alias(
                targets.LoadBalancerTarget(dr_alb_dns)
            ),
            set_identifier="DR",
            failover=route53.FailoverPolicy.SECONDARY
        )

        # CloudWatch Alarm for Primary Region Health
        primary_alarm = cloudwatch.Alarm(self, "PrimaryRegionAlarm",
            metric=cloudwatch.Metric(
                namespace="AWS/Route53",
                metric_name="HealthCheckStatus",
                dimensions_map={
                    "HealthCheckId": self.primary_health_check.attr_health_check_id
                }
            ),
            threshold=1,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD
        )

        # Lambda function for automated DR activation
        dr_orchestrator_role = iam.Role(self, "DROrchestratorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "DROrchestratorPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "lambda:InvokeFunction",
                                "sns:Publish",
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

        self.dr_orchestrator = lambda_.Function(self, "DROrchestratorFunction",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            role=dr_orchestrator_role,
            code=lambda_.Code.from_inline("""
import boto3
import json
import os

def handler(event, context):
    sns = boto3.client('sns')
    lambda_client = boto3.client('lambda', region_name='us-west-2')
    
    # Send notification
    sns.publish(
        TopicArn=os.environ['SNS_TOPIC_ARN'],
        Subject='DR Activation Triggered',
        Message='Primary region health check failed. Initiating DR procedures.'
    )
    
    # Invoke DR activation function in DR region
    lambda_client.invoke(
        FunctionName=os.environ['DR_FUNCTION_ARN'],
        InvocationType='Event',
        Payload=json.dumps({
            'asg_name': os.environ['DR_ASG_NAME'],
            'replica_id': os.environ['DR_REPLICA_ID']
        })
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps('DR orchestration initiated')
    }
            """),
            environment={
                "SNS_TOPIC_ARN": self.dr_notification_topic.topic_arn
            },
            timeout=Duration.minutes(5)
        )

        # CloudWatch Event Rule to trigger DR on alarm
        dr_trigger_rule = events.Rule(self, "DRTriggerRule",
            event_pattern=events.EventPattern(
                source=["aws.cloudwatch"],
                detail_type=["CloudWatch Alarm State Change"],
                detail={
                    "alarmName": [primary_alarm.alarm_name],
                    "state": {
                        "value": ["ALARM"]
                    }
                }
            )
        )

        dr_trigger_rule.add_target(event_targets.LambdaFunction(self.dr_orchestrator))