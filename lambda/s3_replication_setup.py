import boto3
import json


def setup_s3_cross_region_replication(
    source_bucket, destination_bucket, source_region, dest_region
):
    """
    Sets up S3 cross-region replication between primary and DR regions
    """
    s3_client = boto3.client("s3", region_name=source_region)

    # Create replication role
    iam = boto3.client("iam")

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "s3.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    replication_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObjectVersionForReplication", "s3:GetObjectVersionAcl"],
                "Resource": f"arn:aws:s3:::{source_bucket}/*",
            },
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": f"arn:aws:s3:::{source_bucket}",
            },
            {
                "Effect": "Allow",
                "Action": ["s3:ReplicateObject", "s3:ReplicateDelete"],
                "Resource": f"arn:aws:s3:::{destination_bucket}/*",
            },
        ],
    }

    # Create IAM role for replication
    try:
        role_response = iam.create_role(
            RoleName="S3ReplicationRole",
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for S3 cross-region replication",
        )
        role_arn = role_response["Role"]["Arn"]

        # Attach policy to role
        iam.put_role_policy(
            RoleName="S3ReplicationRole",
            PolicyName="S3ReplicationPolicy",
            PolicyDocument=json.dumps(replication_policy),
        )

    except iam.exceptions.EntityAlreadyExistsException:
        role_arn = f"arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/S3ReplicationRole"

    # Configure replication
    replication_config = {
        "Role": role_arn,
        "Rules": [
            {
                "ID": "ReplicateToDR",
                "Status": "Enabled",
                "Priority": 1,
                "Filter": {"Prefix": ""},
                "Destination": {
                    "Bucket": f"arn:aws:s3:::{destination_bucket}",
                    "StorageClass": "STANDARD_IA",
                },
            }
        ],
    }

    s3_client.put_bucket_replication(
        Bucket=source_bucket, ReplicationConfiguration=replication_config
    )

    print(f"Cross-region replication configured from {source_bucket} to {destination_bucket}")


if __name__ == "__main__":
    # Example usage
    setup_s3_cross_region_replication(
        source_bucket="primary-app-data-bucket",
        destination_bucket="dr-app-data-bucket",
        source_region="us-east-1",
        dest_region="us-west-2",
    )
