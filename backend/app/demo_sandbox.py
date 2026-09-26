import os
import boto3
from typing import Optional

_moto_mock = None
_is_demo_mode = False

def is_demo_active() -> bool:
    return _is_demo_mode

def activate_demo_sandbox(region: str = "us-east-1"):
    """
    Activates the live in-process AWS simulation engine (Moto).
    Initializes a realistic set of AWS infrastructure (EC2, EBS, ELB, S3, RDS, EIP, Lambda).
    All boto3 calls interact with live, real-time emulated cloud APIs.
    """
    global _moto_mock, _is_demo_mode
    if not _is_demo_mode:
        from moto import mock_aws
        _moto_mock = mock_aws()
        _moto_mock.start()
        _is_demo_mode = True

        os.environ["AWS_ACCESS_KEY_ID"] = "DEMO_ACCESS_KEY_ID"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "DEMO_SECRET_ACCESS_KEY"
        os.environ["AWS_DEFAULT_REGION"] = region

        _seed_live_resources(region)

def _seed_live_resources(region: str):
    """Seeds live active cloud infrastructure into the emulated AWS account"""
    session = boto3.Session(
        aws_access_key_id="DEMO_ACCESS_KEY_ID",
        aws_secret_access_key="DEMO_SECRET_ACCESS_KEY",
        region_name=region
    )
    ec2 = session.client('ec2')
    elbv2 = session.client('elbv2')
    s3 = session.client('s3')
    rds = session.client('rds')

    try:
        # 1. Idle EC2 compute instance
        ec2.run_instances(
            ImageId='ami-0c55b159cbfafe1f0',
            InstanceType='t3.xlarge',
            MinCount=1, MaxCount=1,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Name', 'Value': 'dev-idle-analytics-worker'},
                    {'Key': 'Environment', 'Value': 'Development'},
                    {'Key': 'Owner', 'Value': 'Engineering'}
                ]
            }]
        )
    except Exception as e:
        print(f"Demo EC2 seed warning: {e}")

    try:
        # 2. Orphaned unattached EBS storage volume
        ec2.create_volume(
            AvailabilityZone=f"{region}a",
            Size=120,
            VolumeType='gp2',
            TagSpecifications=[{
                'ResourceType': 'volume',
                'Tags': [
                    {'Key': 'Name', 'Value': 'orphaned-archive-snapshot-disk'},
                    {'Key': 'Environment', 'Value': 'Staging'}
                ]
            }]
        )
    except Exception as e:
        print(f"Demo EBS seed warning: {e}")

    try:
        # 3. Unassociated Elastic IP
        ec2.allocate_address(Domain='vpc')
    except Exception as e:
        print(f"Demo EIP seed warning: {e}")

    try:
        # 4. S3 Bucket
        s3.create_bucket(Bucket='cloudscope-dev-temp-bucket-2026')
    except Exception as e:
        print(f"Demo S3 seed warning: {e}")

    try:
        # 5. RDS Instance
        rds.create_db_instance(
            DBInstanceIdentifier='dev-postgres-db-abandoned',
            DBInstanceClass='db.t3.medium',
            Engine='postgres',
            AllocatedStorage=20,
            MasterUsername='dbadmin',
            MasterUserPassword='TemporaryPassword123!'
        )
        rds.stop_db_instance(DBInstanceIdentifier='dev-postgres-db-abandoned')
    except Exception as e:
        print(f"Demo RDS seed warning: {e}")
