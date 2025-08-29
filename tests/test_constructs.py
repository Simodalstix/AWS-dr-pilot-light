import pytest
from config.environments import PRODUCTION_CONFIG


class TestEnvironmentConfig:
    """Test environment configuration"""

    def test_production_config(self):
        """Test production configuration is valid"""
        config = PRODUCTION_CONFIG

        assert config.environment_name == "production"
        assert config.primary_region.region == "ap-southeast-2"
        assert config.dr_region.region == "ap-southeast-1"
        assert config.database.encrypted is True
        assert config.enable_deletion_protection is True

    def test_regions_are_different(self):
        """Test primary and DR regions are different"""
        config = PRODUCTION_CONFIG

        assert config.primary_region.region != config.dr_region.region

    def test_vpc_cidrs_are_different(self):
        """Test VPC CIDRs don't overlap"""
        config = PRODUCTION_CONFIG

        assert config.primary_region.vpc_cidr != config.dr_region.vpc_cidr
