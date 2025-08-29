from aws_cdk import (
    aws_wafv2 as waf,
    aws_guardduty as guardduty,
    aws_securityhub as securityhub,
    aws_config as config,
    aws_iam as iam,
    aws_sns as sns,
    RemovalPolicy,
)
from constructs import Construct


class SecurityStack(Construct):
    """
    Comprehensive security stack with WAF, GuardDuty, Security Hub, and Config
    """

    def __init__(
        self, scope: Construct, construct_id: str, notification_topic: sns.Topic, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # WAF Web ACL
        self.web_acl = waf.CfnWebACL(
            self,
            "WebACL",
            scope="REGIONAL",
            default_action=waf.CfnWebACL.DefaultActionProperty(allow={}),
            rules=[
                # Rate limiting
                waf.CfnWebACL.RuleProperty(
                    name="RateLimitRule",
                    priority=1,
                    statement=waf.CfnWebACL.StatementProperty(
                        rate_based_statement=waf.CfnWebACL.RateBasedStatementProperty(
                            limit=2000, aggregate_key_type="IP"
                        )
                    ),
                    action=waf.CfnWebACL.RuleActionProperty(block={}),
                    visibility_config=waf.CfnWebACL.VisibilityConfigProperty(
                        sampled_requests_enabled=True,
                        cloud_watch_metrics_enabled=True,
                        metric_name="RateLimitRule",
                    ),
                ),
                # AWS Managed Rules
                waf.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=2,
                    override_action=waf.CfnWebACL.OverrideActionProperty(none={}),
                    statement=waf.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=waf.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS", name="AWSManagedRulesCommonRuleSet"
                        )
                    ),
                    visibility_config=waf.CfnWebACL.VisibilityConfigProperty(
                        sampled_requests_enabled=True,
                        cloud_watch_metrics_enabled=True,
                        metric_name="CommonRuleSetMetric",
                    ),
                ),
            ],
            visibility_config=waf.CfnWebACL.VisibilityConfigProperty(
                sampled_requests_enabled=True,
                cloud_watch_metrics_enabled=True,
                metric_name="WebACL",
            ),
        )

        # GuardDuty Detector
        self.guardduty_detector = guardduty.CfnDetector(
            self, "GuardDutyDetector", enable=True, finding_publishing_frequency="FIFTEEN_MINUTES"
        )

        # Security Hub
        self.security_hub = securityhub.CfnHub(self, "SecurityHub")

        # Config Configuration Recorder
        self._setup_config_rules()

    def _setup_config_rules(self):
        """Setup AWS Config rules for compliance monitoring"""

        # Service role for Config
        config_role = iam.Role(
            self,
            "ConfigRole",
            assumed_by=iam.ServicePrincipal("config.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/ConfigRole")
            ],
        )

        # Configuration Recorder
        config_recorder = config.CfnConfigurationRecorder(
            self,
            "ConfigRecorder",
            role_arn=config_role.role_arn,
            recording_group=config.CfnConfigurationRecorder.RecordingGroupProperty(
                all_supported=True, include_global_resource_types=True
            ),
        )

        # Delivery Channel (simplified - would need S3 bucket in production)
        # This is a placeholder - in production you'd create an S3 bucket for Config

        # Essential Config Rules
        config.CfnConfigRule(
            self,
            "RootMFAEnabledRule",
            source=config.CfnConfigRule.SourceProperty(
                owner="AWS", source_identifier="ROOT_MFA_ENABLED"
            ),
        )

        config.CfnConfigRule(
            self,
            "RDSEncryptedRule",
            source=config.CfnConfigRule.SourceProperty(
                owner="AWS", source_identifier="RDS_STORAGE_ENCRYPTED"
            ),
        )
