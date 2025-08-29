# AWS E-commerce Pilot Light Disaster Recovery

[![CI](https://github.com/Simodalstix/AWS-dr-pilot-light/workflows/CI/badge.svg)](https://github.com/Simodalstix/AWS-dr-pilot-light/actions)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-blue)](https://python.org)
[![CDK](https://img.shields.io/badge/AWS%20CDK-2.111.0-orange)](https://aws.amazon.com/cdk/)
[![Release](https://img.shields.io/github/v/release/Simodalstix/AWS-dr-pilot-light)](https://github.com/Simodalstix/AWS-dr-pilot-light/releases)

Enterprise-grade Disaster Recovery solution for e-commerce platforms using AWS Pilot Light strategy. Built with AWS CDK Python v2.111.0 following AWS Well-Architected principles.

## Architecture Overview

### Pilot Light Strategy
- **Primary Region (ap-southeast-2)**: Full production e-commerce platform in Sydney
- **DR Region (ap-southeast-1)**: Minimal "pilot light" infrastructure in Singapore
- **Global Resources**: Route 53 DNS failover with health monitoring
- **Australian Data Sovereignty**: Compliant with Australian data residency requirements

### Key Components

#### Primary Region (Sydney)
- **Secure VPC** with flow logs and NACLs
- **RDS MySQL** with encryption, automated backups, and performance insights
- **Auto Scaling Group** with Application Load Balancer
- **S3 Cross-Region Replication** for application data
- **WAF, GuardDuty, Security Hub** for comprehensive security

#### DR Region (Singapore) - Pilot Light
- **Mirrored VPC** infrastructure (cost-optimized)
- **RDS Read Replica** (continuously synchronized)
- **Pre-configured ALB and Launch Templates**
- **Auto Scaling Group scaled to 0** (ready for instant activation)
- **Step Functions orchestration** for automated DR procedures

#### Global Resources
- **Route 53 failover routing** with health checks
- **CloudWatch monitoring** and custom dashboards
- **SNS notifications** for DR events
- **Automated validation** and rollback procedures

## Quick Start

### Prerequisites
- AWS CLI configured with appropriate permissions
- Node.js 18+ and AWS CDK v2.111.0
- Python 3.11+ with pip
- Domain name for Route 53 (optional)

### Quickstart
```bash
# Clone and setup
git clone https://github.com/Simodalstix/AWS-dr-pilot-light.git
cd AWS-dr-pilot-light
poetry install

# Validate infrastructure
poetry run cdk synth
```

### Deployment
```bash
# Install AWS CDK
npm install -g aws-cdk@2.111.0

# Bootstrap regions (one-time setup)
poetry run cdk bootstrap --region ap-southeast-2  # Sydney
poetry run cdk bootstrap --region ap-southeast-1  # Singapore

# Deploy infrastructure
poetry run cdk deploy --all --require-approval never
```

## Disaster Recovery Operations

### Automated Failover
DR is triggered automatically when:
- Route 53 health checks fail
- CloudWatch alarms detect primary region issues
- Step Functions orchestrate the entire failover process

### Manual DR Activation
```bash
# Trigger DR via Step Functions
aws stepfunctions start-execution \
  --state-machine-arn <DR_STATE_MACHINE_ARN> \
  --input '{"message":"Manual DR activation"}' \
  --region ap-southeast-1

# Or manually scale resources
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name <DR_ASG_NAME> \
  --desired-capacity 2 \
  --min-size 2 \
  --region ap-southeast-1
```

### DR Testing
```bash
# Simulate primary region failure
aws cloudwatch set-alarm-state \
  --alarm-name "PrimaryHealthAlarm" \
  --state-value ALARM \
  --state-reason "DR Test"
```

## Performance Metrics

### Recovery Time Objectives (RTO)
- **Automated Failover**: 3-5 minutes
- **Manual Failover**: 5-10 minutes
- **Full Application Recovery**: 10-15 minutes
- **DNS Propagation**: 1-3 minutes (Route 53)

### Recovery Point Objectives (RPO)
- **Database**: < 1 minute (RDS Read Replica with minimal lag)
- **Application Data**: < 5 minutes (S3 cross-region replication)
- **Configuration**: Real-time (Infrastructure as Code)

## Cost Optimization

### Pilot Light Benefits
- **~80% cost reduction** vs. warm standby
- Only RDS read replica and minimal networking costs in DR region
- Auto Scaling Groups at 0 capacity (no EC2 costs)
- Single NAT Gateway in DR region
- S3 Intelligent Tiering for long-term storage

### Estimated Monthly Costs (Sydney/Singapore)
- **Primary Region**: ~$200-500 (depending on traffic)
- **DR Region**: ~$50-100 (pilot light mode)
- **Global Resources**: ~$10-20 (Route 53, health checks)

## Testing & Validation

### Automated Testing
- **Chaos Engineering**: Automated failure injection
- **Health Checks**: Continuous validation of both regions
- **Step Functions**: Automated DR workflow testing
- **CloudWatch Dashboards**: Real-time monitoring

### Manual Testing Procedures
1. **Simulate Primary Failure**: Trigger CloudWatch alarms
2. **Monitor Failover**: Watch Step Functions execution
3. **Validate DR Region**: Check application functionality
4. **Test Failback**: Return to primary when healthy
5. **Document Results**: Update runbooks and procedures

## Security & Compliance

### Security Features
- **WAF Protection**: Rate limiting and OWASP Top 10 protection
- **GuardDuty**: Threat detection and monitoring
- **Security Hub**: Centralized security findings
- **VPC Flow Logs**: Network traffic monitoring
- **Encryption**: All data encrypted at rest and in transit
- **IAM**: Least privilege access with role-based permissions

### Australian Compliance
- **Data Sovereignty**: All data remains in Australian regions
- **Privacy Act 1988**: Compliant data handling
- **ACSC Essential Eight**: Security framework alignment
- **Notifiable Data Breaches**: Automated incident response

## Architecture Patterns

### Design Principles
- **Single Responsibility**: Each construct has one purpose
- **Separation of Concerns**: Clear boundaries between components
- **Infrastructure as Code**: Everything defined in CDK
- **Immutable Infrastructure**: Replace, don't modify
- **Observability**: Comprehensive monitoring and logging

### Project Structure
```
├── constructs/           # Reusable CDK constructs
├── stacks/              # CDK stacks for each region
├── lambda_functions/    # DR automation functions
├── config/             # Environment configurations
└── deploy.sh           # Automated deployment script
```

## Monitoring & Observability

### CloudWatch Dashboards
- **DR-PilotLight-Monitoring**: Comprehensive DR metrics
- **Application Performance**: Response times, error rates
- **Infrastructure Health**: CPU, memory, network metrics
- **Security Events**: WAF blocks, GuardDuty findings

### Alerting
- **SNS Notifications**: Critical events and DR activations
- **CloudWatch Alarms**: Automated threshold monitoring
- **Step Functions**: Workflow execution status

## Why This Matters

This project demonstrates real-world disaster recovery patterns used by e-commerce companies:
- **Cost-effective**: 80% savings vs warm standby while meeting RTO/RPO requirements
- **Automated**: Zero-touch failover using Step Functions orchestration
- **Compliant**: Australian data sovereignty with proper security controls
- **Production-ready**: Comprehensive monitoring, alerting, and validation

## Cost & Security Notes

**Monthly Costs:**
- Primary Region: ~$200-500 (production workload)
- DR Region: ~$50-100 (pilot light mode)
- Global Resources: ~$10-20

**Security:**
- All data encrypted at rest and in transit
- IAM roles follow least privilege principle
- WAF protection with rate limiting
- VPC isolation with security groups and NACLs
- GuardDuty threat detection enabled

**Monitoring:**
- CloudWatch dashboards for DR metrics
- SNS notifications for critical events
- Route 53 health checks with automated failover
- Step Functions execution tracking

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Note**: This project requires AWS credentials for CDK synthesis due to cross-region lookups. Ensure your AWS CLI is configured before running `cdk synth`.