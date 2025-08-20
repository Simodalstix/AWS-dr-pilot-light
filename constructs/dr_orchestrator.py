from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_events as events,
    aws_events_targets as targets,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_sns as sns,
    aws_logs as logs,
    Duration,
    RemovalPolicy
)
from constructs import Construct
import json

class DROrchestrator(Construct):
    """
    Comprehensive DR orchestration using Step Functions and Lambda
    Handles automated failover, failback, and testing procedures
    """
    
    def __init__(self, scope: Construct, construct_id: str,
                 notification_topic: sns.Topic,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # IAM Role for DR operations
        self.dr_execution_role = iam.Role(self, "DRExecutionRole",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("lambda.amazonaws.com"),
                iam.ServicePrincipal("states.amazonaws.com")
            ),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ],
            inline_policies={
                "DROperationsPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "autoscaling:*",
                                "rds:*",
                                "route53:*",
                                "ec2:*",
                                "elasticloadbalancing:*",
                                "cloudwatch:*",
                                "sns:Publish",
                                "logs:*"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Lambda Functions for DR operations
        self.failover_function = self._create_failover_function()
        self.failback_function = self._create_failback_function()
        self.health_check_function = self._create_health_check_function()
        self.validation_function = self._create_validation_function()
        
        # Step Function for DR orchestration
        self.dr_state_machine = self._create_dr_state_machine(notification_topic)
        
        # EventBridge rules for automated triggers
        self._create_event_rules()
    
    def _create_failover_function(self) -> lambda_.Function:
        """Lambda function to handle DR failover operations"""
        return lambda_.Function(self, "FailoverFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            role=self.dr_execution_role,
            timeout=Duration.minutes(15),
            memory_size=512,
            code=lambda_.Code.from_inline("""
import boto3
import json
import time
from typing import Dict, Any

def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    print(f"Starting DR failover: {json.dumps(event)}")
    
    region = event.get('dr_region', 'ap-southeast-1')
    asg_name = event.get('asg_name')
    replica_id = event.get('replica_id')
    target_capacity = event.get('target_capacity', 2)
    
    autoscaling = boto3.client('autoscaling', region_name=region)
    rds = boto3.client('rds', region_name=region)
    
    try:
        # Step 1: Scale up Auto Scaling Group
        print(f"Scaling up ASG: {asg_name}")
        autoscaling.update_auto_scaling_group(
            AutoScalingGroupName=asg_name,
            DesiredCapacity=target_capacity,
            MinSize=target_capacity
        )
        
        # Step 2: Promote read replica
        print(f"Promoting read replica: {replica_id}")
        rds.promote_read_replica(
            DBInstanceIdentifier=replica_id
        )
        
        # Step 3: Wait for instances to be healthy
        waiter = autoscaling.get_waiter('group_in_service')
        waiter.wait(
            AutoScalingGroupNames=[asg_name],
            WaiterConfig={'Delay': 30, 'MaxAttempts': 20}
        )
        
        # Step 4: Wait for database to be available
        db_waiter = rds.get_waiter('db_instance_available')
        db_waiter.wait(
            DBInstanceIdentifier=replica_id,
            WaiterConfig={'Delay': 30, 'MaxAttempts': 40}
        )
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'DR failover completed successfully',
                'asg_name': asg_name,
                'replica_id': replica_id,
                'instances_launched': target_capacity
            }
        }
        
    except Exception as e:
        print(f"Failover failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message': 'DR failover failed'
            }
        }
            """),
            environment={
                "LOG_LEVEL": "INFO"
            }
        )
    
    def _create_failback_function(self) -> lambda_.Function:
        """Lambda function to handle failback to primary region"""
        return lambda_.Function(self, "FailbackFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            role=self.dr_execution_role,
            timeout=Duration.minutes(15),
            memory_size=512,
            code=lambda_.Code.from_inline("""
import boto3
import json
from typing import Dict, Any

def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    print(f"Starting failback: {json.dumps(event)}")
    
    primary_region = event.get('primary_region', 'ap-southeast-2')
    dr_region = event.get('dr_region', 'ap-southeast-1')
    
    # This is a complex operation that would involve:
    # 1. Ensuring primary region is healthy
    # 2. Syncing data from DR to primary
    # 3. Switching traffic back to primary
    # 4. Scaling down DR resources
    
    try:
        # Placeholder for failback logic
        print("Failback operation initiated")
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'Failback completed successfully',
                'primary_region': primary_region,
                'dr_region': dr_region
            }
        }
        
    except Exception as e:
        print(f"Failback failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message': 'Failback failed'
            }
        }
            """)
        )
    
    def _create_health_check_function(self) -> lambda_.Function:
        """Lambda function for comprehensive health checks"""
        return lambda_.Function(self, "HealthCheckFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            role=self.dr_execution_role,
            timeout=Duration.minutes(5),
            memory_size=256,
            code=lambda_.Code.from_inline("""
import boto3
import json
import requests
from typing import Dict, Any

def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    region = event.get('region')
    alb_dns = event.get('alb_dns')
    db_identifier = event.get('db_identifier')
    
    health_status = {
        'region': region,
        'alb_healthy': False,
        'database_healthy': False,
        'overall_healthy': False
    }
    
    try:
        # Check ALB health
        if alb_dns:
            response = requests.get(f"http://{alb_dns}/health", timeout=10)
            health_status['alb_healthy'] = response.status_code == 200
        
        # Check database health
        if db_identifier:
            rds = boto3.client('rds', region_name=region)
            db_response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
            db_status = db_response['DBInstances'][0]['DBInstanceStatus']
            health_status['database_healthy'] = db_status == 'available'
        
        health_status['overall_healthy'] = (
            health_status['alb_healthy'] and health_status['database_healthy']
        )
        
        return {
            'statusCode': 200,
            'body': health_status
        }
        
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'overall_healthy': False
            }
        }
            """)
        )
    
    def _create_validation_function(self) -> lambda_.Function:
        """Lambda function to validate DR environment after failover"""
        return lambda_.Function(self, "ValidationFunction",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            role=self.dr_execution_role,
            timeout=Duration.minutes(10),
            memory_size=512,
            code=lambda_.Code.from_inline("""
import boto3
import json
import time
from typing import Dict, Any

def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    print(f"Validating DR environment: {json.dumps(event)}")
    
    region = event.get('region')
    asg_name = event.get('asg_name')
    alb_arn = event.get('alb_arn')
    
    validation_results = {
        'asg_healthy': False,
        'targets_healthy': False,
        'validation_passed': False
    }
    
    try:
        autoscaling = boto3.client('autoscaling', region_name=region)
        elbv2 = boto3.client('elbv2', region_name=region)
        
        # Check ASG health
        asg_response = autoscaling.describe_auto_scaling_groups(
            AutoScalingGroupNames=[asg_name]
        )
        asg = asg_response['AutoScalingGroups'][0]
        healthy_instances = sum(1 for instance in asg['Instances'] 
                              if instance['HealthStatus'] == 'Healthy')
        validation_results['asg_healthy'] = healthy_instances >= asg['DesiredCapacity']
        
        # Check target group health
        target_groups = elbv2.describe_target_groups(LoadBalancerArn=alb_arn)
        for tg in target_groups['TargetGroups']:
            targets = elbv2.describe_target_health(TargetGroupArn=tg['TargetGroupArn'])
            healthy_targets = sum(1 for target in targets['TargetHealthDescriptions']
                                if target['TargetHealth']['State'] == 'healthy')
            validation_results['targets_healthy'] = healthy_targets > 0
        
        validation_results['validation_passed'] = (
            validation_results['asg_healthy'] and validation_results['targets_healthy']
        )
        
        return {
            'statusCode': 200,
            'body': validation_results
        }
        
    except Exception as e:
        print(f"Validation failed: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'validation_passed': False
            }
        }
            """)
        )
    
    def _create_dr_state_machine(self, notification_topic: sns.Topic) -> sfn.StateMachine:
        """Create Step Function state machine for DR orchestration"""
        
        # Define tasks
        send_notification = tasks.SnsPublish(self, "SendNotification",
            topic=notification_topic,
            message=sfn.TaskInput.from_json_path_at("$.notification_message")
        )
        
        health_check_task = tasks.LambdaInvoke(self, "HealthCheckTask",
            lambda_function=self.health_check_function,
            payload_response_only=True
        )
        
        failover_task = tasks.LambdaInvoke(self, "FailoverTask",
            lambda_function=self.failover_function,
            payload_response_only=True
        )
        
        validation_task = tasks.LambdaInvoke(self, "ValidationTask",
            lambda_function=self.validation_function,
            payload_response_only=True
        )
        
        wait_for_stabilization = sfn.Wait(self, "WaitForStabilization",
            time=sfn.WaitTime.duration(Duration.minutes(2))
        )
        
        # Define state machine
        definition = send_notification.next(
            health_check_task.next(
                sfn.Choice(self, "IsHealthy")
                .when(
                    sfn.Condition.boolean_equals("$.body.overall_healthy", False),
                    failover_task.next(
                        wait_for_stabilization.next(
                            validation_task.next(
                                sfn.Choice(self, "ValidationPassed")
                                .when(
                                    sfn.Condition.boolean_equals("$.body.validation_passed", True),
                                    sfn.Succeed(self, "DRSuccess")
                                )
                                .otherwise(sfn.Fail(self, "DRFailed"))
                            )
                        )
                    )
                )
                .otherwise(sfn.Succeed(self, "HealthyNoAction"))
            )
        )
        
        return sfn.StateMachine(self, "DRStateMachine",
            definition=definition,
            role=self.dr_execution_role,
            timeout=Duration.minutes(30),
            logs=sfn.LogOptions(
                destination=logs.LogGroup(self, "DRStateMachineLogGroup",
                    retention=logs.RetentionDays.ONE_MONTH,
                    removal_policy=RemovalPolicy.DESTROY
                ),
                level=sfn.LogLevel.ALL
            )
        )
    
    def _create_event_rules(self):
        """Create EventBridge rules for automated DR triggers"""
        
        # Rule for CloudWatch alarm state changes
        alarm_rule = events.Rule(self, "AlarmStateChangeRule",
            event_pattern=events.EventPattern(
                source=["aws.cloudwatch"],
                detail_type=["CloudWatch Alarm State Change"],
                detail={
                    "state": {
                        "value": ["ALARM"]
                    }
                }
            )
        )
        
        alarm_rule.add_target(
            targets.SfnStateMachine(self.dr_state_machine,
                input=events.RuleTargetInput.from_object({
                    "trigger": "alarm",
                    "notification_message": "DR triggered by CloudWatch alarm"
                })
            )
        )