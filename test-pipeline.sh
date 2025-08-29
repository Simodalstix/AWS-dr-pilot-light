#!/bin/bash

# Local CI Pipeline Test Script
# Runs the same checks as GitHub Actions locally

set -e

echo "🔍 Running local CI pipeline checks..."

# Check prerequisites
echo "📋 Checking prerequisites..."
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry not found. Install with: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi

if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Install Node.js 20+"
    exit 1
fi

echo "✅ Prerequisites check passed"

# Install dependencies
echo "📦 Installing dependencies..."
poetry install

# Install CDK
echo "🔧 Installing AWS CDK..."
npm install -g aws-cdk@2.111.0

# Linting
echo "🔍 Running flake8 linting..."
poetry run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Format check
echo "🎨 Checking code formatting with black..."
poetry run black --check .

# Type checking
echo "🔍 Running mypy type checking..."
poetry run mypy . --ignore-missing-imports

# Run tests
echo "🧪 Running pytest tests..."
poetry run pytest tests/ -v --cov=. --cov-report=term-missing

# CDK Synth
echo "☁️  Running CDK synthesis..."
export AWS_DEFAULT_REGION=ap-southeast-2
poetry run cdk synth --all

echo "✅ All pipeline checks passed! Ready to commit."