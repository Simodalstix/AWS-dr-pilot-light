from dataclasses import dataclass
from typing import Dict, List, Optional
from aws_cdk import Environment

@dataclass
class RegionConfig:
    region: str
    availability_zones: List[str]
    vpc_cidr: str
    nat_gateways: int
    
@dataclass
class DatabaseConfig:
    instance_class: str
    engine_version: str
    backup_retention_days: int
    multi_az: bool
    encrypted: bool
    
@dataclass
class ComputeConfig:
    instance_type: str
    min_capacity: int
    max_capacity: int
    desired_capacity: int
    
@dataclass
class EnvironmentConfig:
    environment_name: str
    primary_region: RegionConfig
    dr_region: RegionConfig
    database: DatabaseConfig
    compute: ComputeConfig
    enable_deletion_protection: bool
    enable_detailed_monitoring: bool
    
# Production Configuration for Australian deployment
PRODUCTION_CONFIG = EnvironmentConfig(
    environment_name="production",
    primary_region=RegionConfig(
        region="ap-southeast-2",  # Sydney - Australian data sovereignty
        availability_zones=["ap-southeast-2a", "ap-southeast-2b", "ap-southeast-2c"],
        vpc_cidr="10.0.0.0/16",
        nat_gateways=3  # High availability
    ),
    dr_region=RegionConfig(
        region="ap-southeast-1",  # Singapore - Regional DR
        availability_zones=["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"],
        vpc_cidr="10.1.0.0/16",
        nat_gateways=2  # Cost optimized pilot light
    ),
    database=DatabaseConfig(
        instance_class="db.r6g.large",
        engine_version="8.0.35",
        backup_retention_days=30,
        multi_az=True,
        encrypted=True
    ),
    compute=ComputeConfig(
        instance_type="m6i.large",
        min_capacity=2,
        max_capacity=20,
        desired_capacity=4
    ),
    enable_deletion_protection=True,
    enable_detailed_monitoring=True
)