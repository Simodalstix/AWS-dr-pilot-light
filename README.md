# AWS Disaster Recovery - Pilot Light Architecture

This project implements a robust Disaster Recovery solution using the Pilot Light strategy with AWS CDK Python v2.111.0.

## Architecture Overview

### Pilot Light Strategy
- **Primary Region (us-east-1)**: Full production environment
- **DR Region (us-west-2)**: Minimal infrastructure with critical data replicated
- **Global Resources**: Route 53 failover and health monitoring

### Key Components

#### Primary Region
- VPC with public/private/database subnets
- RDS MySQL database with automated backups
- Auto Scaling Group with Application Load Balancer
- S3 bucket for application data

#### DR Region (Pilot Light)
- Mirrored VPC infrastructure
- RDS Read Replica (continuously synchronized)
- Pre-configured Launch Templates and ALB
- Auto Scaling Group with 0 capacity (ready to scale)
- Lambda function for DR activation

#### Global Resources
- Route 53 hosted zone with failover routing
- Health checks monitoring primary region
- CloudWatch alarms for automated failover
- SNS notifications for DR events
- Lambda orchestrator for automated DR procedures

## Deployment

### Prerequisites
```bash
# Install AWS CDK
npm install -g aws-cdk

# Install Python dependencies
pip install -r requirements.txt

# Configure AWS credentials
aws configure
```

### Deploy Infrastructure
```bash
# Bootstrap CDK (first time only)
cdk bootstrap --region us-east-1
cdk bootstrap --region us-west-2

# Deploy all stacks
cdk deploy --all
```

### Manual DR Activation
If automated failover doesn't trigger, manually activate DR:

```bash
# Scale up DR Auto Scaling Group
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name DRWebServerASG \
  --desired-capacity 2 \
  --min-size 2 \
  --region us-west-2

# Promote read replica to primary
aws rds promote-read-replica \
  --db-instance-identifier dr-read-replica \
  --region us-west-2
```

## Recovery Time Objectives (RTO)
- **Automated Failover**: 5-10 minutes
- **Manual Failover**: 10-15 minutes
- **Full Application Recovery**: 15-30 minutes

## Recovery Point Objectives (RPO)
- **Database**: < 5 minutes (RDS Read Replica lag)
- **Application Data**: < 15 minutes (S3 cross-region replication)

## Cost Optimization
- DR region runs minimal infrastructure (pilot light)
- RDS read replica is the primary ongoing cost
- Auto Scaling Groups scale to 0 when not needed
- Single NAT Gateway in DR region

## Testing DR Procedures
1. Simulate primary region failure
2. Monitor Route 53 failover
3. Verify DR activation
4. Test application functionality
5. Plan failback procedures

## Security Considerations
- Security groups restrict database access
- IAM roles follow least privilege principle
- VPC isolation between tiers
- Encrypted RDS instances and S3 buckets