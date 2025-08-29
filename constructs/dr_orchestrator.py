from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_sns as sns,
    Duration,
)
from constructs import Construct


class DROrchestrator(Construct):
    """
    DR orchestration using Step Functions and Lambda
    Focused on coordination and workflow management
    """

    def __init__(
        self, scope: Construct, construct_id: str, notification_topic: sns.Topic, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # IAM Role for DR operations
        self.dr_execution_role = iam.Role(
            self,
            "DRExecutionRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("lambda.amazonaws.com"),
                iam.ServicePrincipal("states.amazonaws.com"),
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSLambdaBasicExecutionRole"
                )
            ],
            inline_policies={
                "DROperationsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "autoscaling:UpdateAutoScalingGroup",
                                "rds:PromoteReadReplica",
                                "rds:DescribeDBInstances",
                                "elasticloadbalancing:DescribeTargetHealth",
                                "sns:Publish",
                            ],
                            resources=["*"],
                        )
                    ]
                )
            },
        )

        # Lambda Functions
        self.failover_function = self._create_lambda_function("Failover", "failover.py")
        self.health_check_function = self._create_lambda_function("HealthCheck", "health_check.py")

        # Step Function for DR orchestration
        self.dr_state_machine = self._create_dr_state_machine(notification_topic)

        # EventBridge rules
        self._create_event_rules()

    def _create_lambda_function(self, name: str, filename: str) -> lambda_.Function:
        """Create Lambda function from external file"""
        return lambda_.Function(
            self,
            f"{name}Function",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            role=self.dr_execution_role,
            timeout=Duration.minutes(15),
            memory_size=512,
            code=lambda_.Code.from_asset(f"lambda_functions/{filename}"),
        )

    def _create_dr_state_machine(self, notification_topic: sns.Topic) -> sfn.StateMachine:
        """Create Step Function state machine for DR orchestration"""

        # Define tasks
        notify = tasks.SnsPublish(
            self,
            "Notify",
            topic=notification_topic,
            message=sfn.TaskInput.from_json_path_at("$.message"),
        )

        health_check = tasks.LambdaInvoke(
            self,
            "HealthCheck",
            lambda_function=self.health_check_function,
            payload_response_only=True,
        )

        failover = tasks.LambdaInvoke(
            self, "Failover", lambda_function=self.failover_function, payload_response_only=True
        )

        wait = sfn.Wait(self, "Wait", time=sfn.WaitTime.duration(Duration.minutes(2)))

        # Simple workflow: notify -> check -> failover if needed -> wait -> success
        definition = notify.next(
            health_check.next(
                sfn.Choice(self, "IsHealthy")
                .when(
                    sfn.Condition.boolean_equals("$.body.overall_healthy", False),
                    failover.next(wait.next(sfn.Succeed(self, "Success"))),
                )
                .otherwise(sfn.Succeed(self, "Healthy"))
            )
        )

        return sfn.StateMachine(
            self,
            "DRStateMachine",
            definition=definition,
            role=self.dr_execution_role,
            timeout=Duration.minutes(30),
        )

    def _create_event_rules(self):
        """Create EventBridge rules for automated DR triggers"""

        alarm_rule = events.Rule(
            self,
            "AlarmRule",
            event_pattern=events.EventPattern(
                source=["aws.cloudwatch"],
                detail_type=["CloudWatch Alarm State Change"],
                detail={"state": {"value": ["ALARM"]}},
            ),
        )

        alarm_rule.add_target(
            targets.SfnStateMachine(
                self.dr_state_machine,
                input=events.RuleTargetInput.from_object(
                    {"message": "DR triggered by CloudWatch alarm"}
                ),
            )
        )
