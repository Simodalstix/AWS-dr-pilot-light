from aws_cdk import (
    aws_ec2 as ec2,
    aws_logs as logs,
    RemovalPolicy,
    Tags
)
from constructs import Construct
from typing import Optional

class SecureVpc(Construct):
    """
    Secure VPC construct following AWS Well-Architected principles
    """
    
    def __init__(self, scope: Construct, construct_id: str, 
                 cidr: str = "10.0.0.0/16",
                 enable_flow_logs: bool = True,
                 enable_dns_hostnames: bool = True,
                 enable_dns_support: bool = True,
                 **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # VPC with security-first design
        self.vpc = ec2.Vpc(self, "VPC",
            ip_addresses=ec2.IpAddresses.cidr(cidr),
            max_azs=3,
            nat_gateways=2,  # High availability
            enable_dns_hostnames=enable_dns_hostnames,
            enable_dns_support=enable_dns_support,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ]
        )
        
        # VPC Flow Logs for security monitoring
        if enable_flow_logs:
            self.flow_log_group = logs.LogGroup(self, "VPCFlowLogGroup",
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=RemovalPolicy.DESTROY
            )
            
            self.flow_logs = ec2.FlowLog(self, "VPCFlowLogs",
                resource_type=ec2.FlowLogResourceType.from_vpc(self.vpc),
                destination=ec2.FlowLogDestination.to_cloud_watch_logs(self.flow_log_group)
            )
        
        # Default security group restrictions
        self.vpc.add_flow_log("FlowLogCloudWatch")
        
        # Network ACLs for additional security layer
        self._create_network_acls()
        
        # Tag resources
        Tags.of(self).add("Component", "Networking")
        Tags.of(self).add("Security", "High")
    
    def _create_network_acls(self):
        """Create restrictive Network ACLs"""
        # Private subnet NACL
        private_nacl = ec2.NetworkAcl(self, "PrivateNACL",
            vpc=self.vpc,
            subnet_selection=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            )
        )
        
        # Allow outbound HTTPS
        private_nacl.add_entry("AllowOutboundHTTPS",
            rule_number=100,
            protocol=ec2.AclProtocol.tcp(),
            rule_action=ec2.AclTrafficDirection.EGRESS,
            port_range=ec2.AclPortRange(from_=443, to=443),
            cidr=ec2.AclCidr.any_ipv4()
        )
        
        # Database subnet NACL
        db_nacl = ec2.NetworkAcl(self, "DatabaseNACL",
            vpc=self.vpc,
            subnet_selection=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            )
        )
        
        # Allow MySQL from private subnets only
        for i, subnet in enumerate(self.vpc.private_subnets):
            db_nacl.add_entry(f"AllowMySQLFromPrivate{i}",
                rule_number=100 + i,
                protocol=ec2.AclProtocol.tcp(),
                rule_action=ec2.AclTrafficDirection.INGRESS,
                port_range=ec2.AclPortRange(from_=3306, to=3306),
                cidr=ec2.AclCidr.ipv4(subnet.ipv4_cidr_block)
            )