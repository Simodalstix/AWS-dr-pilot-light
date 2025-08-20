from aws_cdk import (
    Stack,
    aws_sns as sns,
    Tags
)
from constructs import Construct
from constructs.global_dns import GlobalDNS
from config.environments import EnvironmentConfig

class GlobalResourcesStack(Stack):
    def __init__(self, scope: Construct, construct_id: str,
                 config: EnvironmentConfig,
                 primary_alb_dns: str,
                 dr_alb_dns: str,
                 domain_name: str = "ecommerce-dr-demo.com",
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Global SNS Topic for critical alerts
        self.global_notification_topic = sns.Topic(self, "GlobalNotificationTopic",
            display_name="Global DR Notifications"
        )
        
        # Global DNS with Route 53 failover
        self.global_dns = GlobalDNS(self, "GlobalDNS",
            domain_name=domain_name,
            primary_alb_dns=primary_alb_dns,
            dr_alb_dns=dr_alb_dns,
            notification_topic=self.global_notification_topic
        )
        
        # Tags
        Tags.of(self).add("Environment", config.environment_name)
        Tags.of(self).add("Scope", "Global")
        Tags.of(self).add("Application", "E-commerce")