import boto3
import json
import requests
from typing import Dict, Any


def handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Comprehensive health checks for DR validation"""
    region = event.get("region")
    alb_dns = event.get("alb_dns")
    db_identifier = event.get("db_identifier")

    health_status = {
        "region": region,
        "alb_healthy": False,
        "database_healthy": False,
        "overall_healthy": False,
    }

    try:
        # Check ALB health
        if alb_dns:
            response = requests.get(f"http://{alb_dns}/health", timeout=10)
            health_status["alb_healthy"] = response.status_code == 200

        # Check database health
        if db_identifier:
            rds = boto3.client("rds", region_name=region)
            db_response = rds.describe_db_instances(DBInstanceIdentifier=db_identifier)
            db_status = db_response["DBInstances"][0]["DBInstanceStatus"]
            health_status["database_healthy"] = db_status == "available"

        health_status["overall_healthy"] = (
            health_status["alb_healthy"] and health_status["database_healthy"]
        )

        return {"statusCode": 200, "body": health_status}

    except Exception as e:
        return {"statusCode": 500, "body": {"error": str(e), "overall_healthy": False}}
