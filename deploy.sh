#!/bin/bash

# AWS E-commerce Pilot Light DR Deployment Script
# Deploys infrastructure to Australian regions (Sydney primary, Singapore DR)

set -e

echo "🚀 Starting E-commerce Pilot Light DR deployment..."

# Check prerequisites
echo "📋 Checking prerequisites..."
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install AWS CLI."
    exit 1
fi

if ! command -v cdk &> /dev/null; then
    echo "❌ CDK not found. Please install AWS CDK."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run 'aws configure'."
    exit 1
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
PRIMARY_REGION="ap-southeast-2"  # Sydney
DR_REGION="ap-southeast-1"       # Singapore

echo "✅ Prerequisites check passed"
echo "📍 Account: $ACCOUNT_ID"
echo "📍 Primary Region: $PRIMARY_REGION (Sydney)"
echo "📍 DR Region: $DR_REGION (Singapore)"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Bootstrap CDK in both regions
echo "🔧 Bootstrapping CDK..."
echo "   Bootstrapping primary region ($PRIMARY_REGION)..."
cdk bootstrap aws://$ACCOUNT_ID/$PRIMARY_REGION

echo "   Bootstrapping DR region ($DR_REGION)..."
cdk bootstrap aws://$ACCOUNT_ID/$DR_REGION

# Deploy stacks
echo "🏗️  Deploying infrastructure..."

echo "   Deploying primary region stack..."
cdk deploy EcommercePrimaryStack --require-approval never

echo "   Deploying DR region stack..."
cdk deploy EcommerceDRStack --require-approval never

echo "   Deploying global resources..."
cdk deploy EcommerceGlobalStack --require-approval never

echo "✅ Deployment completed successfully!"
echo ""
echo "🎯 Next Steps:"
echo "1. Update Route 53 hosted zone with your domain"
echo "2. Configure SNS topic subscriptions for notifications"
echo "3. Test DR procedures using the provided scripts"
echo "4. Set up monitoring dashboards in CloudWatch"
echo ""
echo "📊 Monitoring:"
echo "- CloudWatch Dashboard: DR-PilotLight-Monitoring"
echo "- Primary ALB: Check health at /health endpoint"
echo "- DR Region: ASG scaled to 0 (pilot light mode)"
echo ""
echo "🔥 To test DR activation:"
echo "aws stepfunctions start-execution --state-machine-arn <DR_STATE_MACHINE_ARN> --input '{\"message\":\"Manual DR test\"}'"