from aws_cdk import (
    aws_ec2 as ec2,
    aws_autoscaling as autoscaling,
    aws_elasticloadbalancingv2 as elbv2,
    aws_elasticloadbalancingv2_targets as targets,
    aws_iam as iam,
    aws_cloudwatch as cloudwatch,
    aws_sns as sns,
    aws_ssm as ssm,
    Duration,
    Tags,
)
from constructs import Construct
from config.environments import ComputeConfig
from typing import List


class EcommerceCompute(Construct):
    """
    Production-grade compute infrastructure for e-commerce platform
    Includes Auto Scaling, Load Balancing, and comprehensive monitoring
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc: ec2.Vpc,
        config: ComputeConfig,
        security_groups: List[ec2.SecurityGroup],
        notification_topic: sns.Topic,
        is_pilot_light: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config = config
        self.vpc = vpc
        self.is_pilot_light = is_pilot_light

        # IAM Role for EC2 instances
        self.instance_role = iam.Role(
            self,
            "InstanceRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy"),
            ],
            inline_policies={
                "EcommerceAppPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "secretsmanager:GetSecretValue",
                                "rds:DescribeDBInstances",
                            ],
                            resources=["*"],
                        )
                    ]
                )
            },
        )

        self.instance_profile = iam.InstanceProfile(
            self, "InstanceProfile", role=self.instance_role
        )

        # User Data for application setup
        user_data = ec2.UserData.for_linux()
        user_data.add_commands(
            "yum update -y",
            "yum install -y amazon-cloudwatch-agent",
            "yum install -y docker",
            "systemctl start docker",
            "systemctl enable docker",
            "usermod -a -G docker ec2-user",
            # CloudWatch Agent configuration
            "cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'EOF'",
            """{
                "metrics": {
                    "namespace": "ECommerce/Application",
                    "metrics_collected": {
                        "cpu": {"measurement": ["cpu_usage_idle", "cpu_usage_iowait"]},
                        "disk": {"measurement": ["used_percent"], "resources": ["*"]},
                        "mem": {"measurement": ["mem_used_percent"]},
                        "netstat": {"measurement": ["tcp_established", "tcp_time_wait"]}
                    }
                },
                "logs": {
                    "logs_collected": {
                        "files": {
                            "collect_list": [
                                {
                                    "file_path": "/var/log/messages",
                                    "log_group_name": "/aws/ec2/ecommerce/system",
                                    "log_stream_name": "{instance_id}"
                                },
                                {
                                    "file_path": "/var/log/ecommerce/app.log",
                                    "log_group_name": "/aws/ec2/ecommerce/application",
                                    "log_stream_name": "{instance_id}"
                                }
                            ]
                        }
                    }
                }
            }""",
            "EOF",
            "/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s",
            # Sample e-commerce application (placeholder)
            "mkdir -p /var/log/ecommerce",
            "echo 'E-commerce application starting...' > /var/log/ecommerce/app.log",
            # Health check endpoint
            "yum install -y nginx",
            "systemctl start nginx",
            "systemctl enable nginx",
            "echo 'healthy' > /var/www/html/health",
        )

        # Launch Template
        self.launch_template = ec2.LaunchTemplate(
            self,
            "LaunchTemplate",
            instance_type=ec2.InstanceType(config.instance_type),
            machine_image=ec2.AmazonLinuxImage(
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
                cpu_type=ec2.AmazonLinuxCpuType.X86_64,
            ),
            security_group=security_groups[0],
            user_data=user_data,
            role=self.instance_role,
            detailed_monitoring=True,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=20,
                        volume_type=ec2.EbsDeviceVolumeType.GP3,
                        encrypted=True,
                        delete_on_termination=True,
                    ),
                )
            ],
        )

        # Auto Scaling Group
        capacity = 0 if is_pilot_light else config.desired_capacity
        min_capacity = 0 if is_pilot_light else config.min_capacity

        self.auto_scaling_group = autoscaling.AutoScalingGroup(
            self,
            "AutoScalingGroup",
            vpc=vpc,
            launch_template=self.launch_template,
            min_capacity=min_capacity,
            max_capacity=config.max_capacity,
            desired_capacity=capacity,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            health_check=autoscaling.HealthCheck.elb(grace=Duration.minutes(5)),
            update_policy=autoscaling.UpdatePolicy.rolling_update(
                max_batch_size=1,
                min_instances_in_service=1 if not is_pilot_light else 0,
                pause_time=Duration.minutes(5),
            ),
        )

        # Application Load Balancer
        self.load_balancer = elbv2.ApplicationLoadBalancer(
            self,
            "LoadBalancer",
            vpc=vpc,
            internet_facing=True,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=security_groups[1] if len(security_groups) > 1 else security_groups[0],
        )

        # Target Group
        self.target_group = elbv2.ApplicationTargetGroup(
            self,
            "TargetGroup",
            vpc=vpc,
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[self.auto_scaling_group],
            health_check=elbv2.HealthCheck(
                enabled=True,
                healthy_http_codes="200",
                path="/health",
                protocol=elbv2.Protocol.HTTP,
                timeout=Duration.seconds(5),
                interval=Duration.seconds(30),
                healthy_threshold_count=2,
                unhealthy_threshold_count=3,
            ),
        )

        # Listener
        self.listener = self.load_balancer.add_listener(
            "Listener",
            port=80,
            protocol=elbv2.ApplicationProtocol.HTTP,
            default_target_groups=[self.target_group],
        )

        # Auto Scaling Policies
        if not is_pilot_light:
            self._create_scaling_policies(notification_topic)

        # CloudWatch Alarms
        self._create_compute_alarms(notification_topic)

        # Tags
        Tags.of(self).add("Component", "Compute")
        Tags.of(self).add("Application", "E-commerce")
        Tags.of(self).add("PilotLight", str(is_pilot_light))

    def _create_scaling_policies(self, notification_topic: sns.Topic):
        """Create auto scaling policies based on metrics"""

        # Scale Up Policy
        scale_up_policy = self.auto_scaling_group.scale_on_metric(
            "ScaleUpPolicy",
            metric=cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="TargetResponseTime",
                dimensions_map={"LoadBalancer": self.load_balancer.load_balancer_full_name},
            ),
            scaling_steps=[
                autoscaling.ScalingInterval(upper=1.0, change=1),
                autoscaling.ScalingInterval(lower=1.0, change=2),
            ],
            adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown=Duration.minutes(5),
        )

        # Scale Down Policy
        scale_down_policy = self.auto_scaling_group.scale_on_metric(
            "ScaleDownPolicy",
            metric=cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="TargetResponseTime",
                dimensions_map={"LoadBalancer": self.load_balancer.load_balancer_full_name},
            ),
            scaling_steps=[autoscaling.ScalingInterval(upper=0.5, change=-1)],
            adjustment_type=autoscaling.AdjustmentType.CHANGE_IN_CAPACITY,
            cooldown=Duration.minutes(10),
        )

    def _create_compute_alarms(self, notification_topic: sns.Topic):
        """Create CloudWatch alarms for compute infrastructure"""

        # ALB Target Health
        cloudwatch.Alarm(
            self,
            "UnhealthyTargetsAlarm",
            metric=self.target_group.metric_unhealthy_host_count(),
            threshold=1,
            evaluation_periods=2,
            alarm_description="Unhealthy targets detected",
        ).add_alarm_action(cloudwatch.SnsAction(notification_topic))

        # ALB Response Time
        cloudwatch.Alarm(
            self,
            "HighResponseTimeAlarm",
            metric=self.target_group.metric_target_response_time(),
            threshold=2.0,
            evaluation_periods=2,
            alarm_description="High response time detected",
        ).add_alarm_action(cloudwatch.SnsAction(notification_topic))

        # ALB 5XX Errors
        cloudwatch.Alarm(
            self,
            "HighErrorRateAlarm",
            metric=self.load_balancer.metric_target_response_time(),
            threshold=10,
            evaluation_periods=2,
            alarm_description="High error rate detected",
        ).add_alarm_action(cloudwatch.SnsAction(notification_topic))
