import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from . import models, crypto

def resolve_aws_session(
    db: Optional[Session] = None,
    explicit_key: Optional[str] = None,
    explicit_secret: Optional[str] = None,
    explicit_region: Optional[str] = None
) -> Tuple[boto3.Session, Dict[str, Any]]:
    """
    Resolves AWS credentials using standard boto3 resolution order:
    1. Explicit arguments if provided
    2. Stored DB configuration (encrypted) if present and configured
    3. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.)
    4. AWS Profile / IAM Role / EC2 Metadata / ECS credentials via default boto3 Session
    """
    # Sanitize empty environment variables that corrupt Boto3 profile lookup
    if not os.environ.get("AWS_PROFILE"):
        os.environ.pop("AWS_PROFILE", None)
    if not os.environ.get("AWS_DEFAULT_PROFILE"):
        os.environ.pop("AWS_DEFAULT_PROFILE", None)

    region = explicit_region or os.environ.get("AWS_REGION") or "us-east-1"
    auth_source = "default_chain"
    session = None

    from .demo_sandbox import activate_demo_sandbox, is_demo_active

    is_demo_requested = (
        (explicit_key and ("@" in explicit_key or "demo" in explicit_key.lower() or explicit_key.lower() == "test"))
        or (db is not None and db.query(models.UserSetting).first() and db.query(models.UserSetting).first().auth_mode == "demo")
        or is_demo_active()
    )

    # Demo sandbox mode
    if is_demo_requested:
        activate_demo_sandbox(region)
        session = boto3.Session(
            aws_access_key_id="DEMO_ACCESS_KEY_ID",
            aws_secret_access_key="DEMO_SECRET_ACCESS_KEY",
            region_name=region
        )
        auth_source = "live_demo_sandbox"

    # 1. Explicit arguments provided
    elif explicit_key and explicit_secret:
        session = boto3.Session(
            aws_access_key_id=explicit_key,
            aws_secret_access_key=explicit_secret,
            region_name=region
        )
        auth_source = "explicit_credentials"

    # 2. Stored DB configuration
    elif db is not None:
        db_config = db.query(models.UserSetting).first()
        if db_config and db_config.is_configured and db_config.aws_access_key and db_config.aws_secret_key:
            try:
                decrypted_secret = crypto.decrypt(db_config.aws_secret_key)
                session = boto3.Session(
                    aws_access_key_id=db_config.aws_access_key,
                    aws_secret_access_key=decrypted_secret,
                    region_name=db_config.aws_region or region
                )
                region = db_config.aws_region or region
                auth_source = "stored_encrypted_credentials"
            except Exception as e:
                # Decryption error or invalid config, fall back to environment chain
                auth_source = "fallback_env_chain"

    # 3. Environment or IAM Role / Profile chain (Default Boto3 chain)
    if session is None:
        profile = os.environ.get("AWS_PROFILE")
        if profile:
            session = boto3.Session(profile_name=profile, region_name=region)
            auth_source = f"aws_profile_{profile}"
        else:
            session = boto3.Session(region_name=region)
            auth_source = "environment_or_iam_role"

    # Verify identity via STS
    metadata = {
        "auth_source": auth_source,
        "region": session.region_name or region,
        "is_authenticated": False,
        "account_id": None,
        "arn": None,
        "user_id": None,
        "error": None
    }

    try:
        sts = session.client('sts')
        caller = sts.get_caller_identity()
        metadata["is_authenticated"] = True
        metadata["account_id"] = caller.get("Account")
        metadata["arn"] = caller.get("Arn")
        metadata["user_id"] = caller.get("UserId")
    except NoCredentialsError:
        metadata["error"] = "No AWS credentials found in environment, profile, or storage."
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "UnknownError")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        metadata["error"] = f"AWS STS Authentication failed ({error_code}): {error_msg}"
    except Exception as e:
        metadata["error"] = f"Authentication check failed: {str(e)}"

    return session, metadata

def check_aws_permissions(session: boto3.Session) -> Dict[str, Any]:
    """
    Two-phase permission validation:
    Checks READ permissions (discovery & analysis) and ACTION permissions (destructive).
    Does NOT execute any destructive actions during checks.
    """
    results = {
        "read_permissions": {
            "ec2:DescribeInstances": False,
            "ec2:DescribeVolumes": False,
            "elasticloadbalancing:DescribeLoadBalancers": False,
            "cloudwatch:GetMetricStatistics": False,
            "ce:GetCostAndUsage": False
        },
        "action_permissions": {
            "ec2:TerminateInstances": False,
            "ec2:DeleteVolume": False,
            "elasticloadbalancing:DeleteLoadBalancer": False
        },
        "missing_read_permissions": [],
        "warnings": []
    }

    # Test EC2 Describe
    try:
        ec2 = session.client('ec2')
        ec2.describe_instances(MaxResults=5)
        results["read_permissions"]["ec2:DescribeInstances"] = True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if "UnauthorizedOperation" in code or "AccessDenied" in code:
            results["missing_read_permissions"].append("ec2:DescribeInstances")
        results["warnings"].append(f"EC2 DescribeInstances warning: {code}")
    except Exception as e:
        results["warnings"].append(f"EC2 check error: {str(e)}")

    # Test EBS Describe
    try:
        ec2 = session.client('ec2')
        ec2.describe_volumes(MaxResults=5)
        results["read_permissions"]["ec2:DescribeVolumes"] = True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if "UnauthorizedOperation" in code or "AccessDenied" in code:
            results["missing_read_permissions"].append("ec2:DescribeVolumes")
        results["warnings"].append(f"EBS DescribeVolumes warning: {code}")
    except Exception:
        pass

    # Test ELBv2 Describe
    try:
        elbv2 = session.client('elbv2')
        elbv2.describe_load_balancers(PageSize=5)
        results["read_permissions"]["elasticloadbalancing:DescribeLoadBalancers"] = True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if "AccessDenied" in code:
            results["missing_read_permissions"].append("elasticloadbalancing:DescribeLoadBalancers")
        results["warnings"].append(f"ELB Describe warning: {code}")
    except Exception:
        pass

    # Test Cost Explorer
    try:
        ce = session.client('ce')
        import datetime
        today = datetime.date.today()
        start = (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
        end = (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        ce.get_cost_and_usage(
            TimePeriod={'Start': start, 'End': end},
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )
        results["read_permissions"]["ce:GetCostAndUsage"] = True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        results["warnings"].append(f"AWS Cost Explorer not accessible ({code}). Resource pricing estimates will be used.")
    except Exception:
        pass

    return results
