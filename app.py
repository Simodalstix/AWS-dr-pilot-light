#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.primary_region_stack import PrimaryRegionStack
from stacks.dr_region_stack import DRRegionStack
from stacks.global_resources_stack import GlobalResourcesStack
from config.environments import PRODUCTION_CONFIG

app = cdk.App()

# Get environment from context or use production as default
env_name = app.node.try_get_context("environment") or "production"
config = PRODUCTION_CONFIG  # Could extend to support multiple environments

# Primary region (Sydney for Australian data sovereignty)
primary_stack = PrimaryRegionStack(
    app,
    "EcommercePrimaryStack",
    config=config,
    env=cdk.Environment(region=config.primary_region.region, account=app.account),
    description="E-commerce primary region infrastructure (Sydney)",
)

# DR region (Singapore for regional DR)
dr_stack = DRRegionStack(
    app,
    "EcommerceDRStack",
    config=config,
    primary_database=primary_stack.database,
    env=cdk.Environment(region=config.dr_region.region, account=app.account),
    description="E-commerce DR region infrastructure (Singapore) - Pilot Light",
)

# Global resources (Route 53, etc.)
global_stack = GlobalResourcesStack(
    app,
    "EcommerceGlobalStack",
    config=config,
    primary_alb_dns=primary_stack.load_balancer.load_balancer_dns_name,
    dr_alb_dns=dr_stack.load_balancer.load_balancer_dns_name,
    env=cdk.Environment(
        region=config.primary_region.region,  # Global resources in primary region
        account=app.account,
    ),
    description="E-commerce global resources (Route 53, DNS)",
)

# Stack dependencies
dr_stack.add_dependency(primary_stack)
global_stack.add_dependency(primary_stack)
global_stack.add_dependency(dr_stack)

app.synth()
