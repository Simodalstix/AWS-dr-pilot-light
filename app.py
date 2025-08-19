#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.primary_region_stack import PrimaryRegionStack
from stacks.dr_region_stack import DRRegionStack
from stacks.global_resources_stack import GlobalResourcesStack

app = cdk.App()

# Primary region (us-east-1)
primary_stack = PrimaryRegionStack(
    app, "PrimaryRegionStack",
    env=cdk.Environment(region="us-east-1")
)

# DR region (us-west-2)
dr_stack = DRRegionStack(
    app, "DRRegionStack",
    primary_vpc_id=primary_stack.vpc.vpc_id,
    primary_db_instance=primary_stack.database,
    env=cdk.Environment(region="us-west-2")
)

# Global resources (Route 53, etc.)
global_stack = GlobalResourcesStack(
    app, "GlobalResourcesStack",
    primary_alb_dns=primary_stack.load_balancer.load_balancer_dns_name,
    dr_alb_dns=dr_stack.load_balancer.load_balancer_dns_name,
    env=cdk.Environment(region="us-east-1")  # Global resources in primary region
)

app.synth()