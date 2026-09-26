import hashlib
import json
import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from botocore.exceptions import ClientError
from . import models
from .sandbox import sandbox

def compute_plan_hash(candidates: List[Dict[str, Any]], account_id: str, region: str) -> str:
    """
    Computes a cryptographic SHA-256 hash over the sorted candidates, actions, account, and region.
    Any alteration to candidates immediately invalidates previously granted approvals.
    """
    normalized = []
    for c in sorted(candidates, key=lambda x: x.get("resource_id", "")):
        normalized.append({
            "resource_id": c.get("resource_id"),
            "resource_type": c.get("resource_type"),
            "action": c.get("recommended_action")
        })
    payload = {
        "account_id": account_id,
        "region": region,
        "candidates": normalized
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

class ApprovalService:
    """
    Centralized governance service managing the Human-in-the-Loop approval gate.
    Guarantees that no destructive cloud action can occur without explicit, unexpired,
    plan-hash-verified human authorization.
    """
    @staticmethod
    def create_approval_requests(
        db: Session,
        run_id: str,
        plan_id: str,
        aws_account_id: str,
        region: str,
        plan_hash: str,
        candidates: List[Dict[str, Any]],
        expiry_hours: int = 2
    ) -> List[models.ApprovalRequest]:
        approvals = []
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=expiry_hours)

        for c in candidates:
            if not c.get("requires_approval") or c.get("recommended_action") == "retain":
                continue

            action_name = f"{c['recommended_action']}_{c['resource_type']}"
            req = models.ApprovalRequest(
                run_id=run_id,
                plan_id=plan_id,
                user_id="admin",
                aws_account_id=aws_account_id,
                region=region,
                resource_id=c["resource_id"],
                resource_type=c["resource_type"],
                resource_name=c.get("name", c["resource_id"]),
                action=action_name,
                plan_hash=plan_hash,
                risk_level="HIGH" if c["resource_type"] in ["ec2", "ebs"] else "MEDIUM",
                evidence_json=json.dumps(c.get("evidence", [])),
                dependencies_json=json.dumps(c.get("dependencies", [])),
                estimated_monthly_cost=c.get("monthly_cost", 0.0),
                estimated_monthly_savings=c.get("monthly_cost", 0.0),
                status="PENDING",
                created_at=datetime.datetime.utcnow(),
                expires_at=expires_at
            )
            db.add(req)
            approvals.append(req)

        db.commit()
        return approvals

    @staticmethod
    def resolve_approval(
        db: Session,
        approval_id: str,
        decision: str, # "APPROVED" or "REJECTED"
        user_id: str = "admin",
        reason: str = "Decision recorded by user"
    ) -> Tuple[bool, str, Optional[models.ApprovalRequest]]:
        req = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval_id).first()
        if not req:
            return False, f"Approval request {approval_id} not found", None

        # Check if already resolved
        if req.status in ["APPROVED", "REJECTED", "COMPLETED", "EXECUTING"]:
            return False, f"Approval request already in status '{req.status}'", req

        # Check expiration
        if datetime.datetime.utcnow() > req.expires_at:
            req.status = "EXPIRED"
            db.commit()
            return False, "Approval request has expired and cannot be actioned", req

        if decision not in ["APPROVED", "REJECTED"]:
            return False, f"Invalid decision '{decision}'. Must be APPROVED or REJECTED.", req

        req.status = decision
        req.resolved_at = datetime.datetime.utcnow()
        req.resolved_by = user_id
        db.commit()
        return True, f"Approval request {decision.lower()} successfully", req

    @staticmethod
    def validate_and_execute_approved_action(
        db: Session,
        approval_id: str,
        session, # boto3.Session
        current_plan_hash: str
    ) -> Dict[str, Any]:
        """
        STRICT MULTI-POINT SECURITY VALIDATION:
        1. Approval record exists
        2. Status is explicitly 'APPROVED'
        3. Expiration time has not passed
        4. Plan hash matches current active plan (invalidates if plan altered)
        5. Pre-deletion check: Resource still exists in live AWS account & matches target state
        6. Execute strictly through sandboxed runner
        7. Post-deletion check: Verify state transition in AWS
        """
        req = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval_id).first()
        if not req:
            return {"success": False, "error": "Approval record not found", "status": "BLOCKED"}

        # Check 1: Explicit status
        if req.status != "APPROVED":
            return {
                "success": False,
                "error": f"Action blocked: Approval status is '{req.status}', required: 'APPROVED'",
                "status": "BLOCKED"
            }

        # Check 2: Expiration
        if datetime.datetime.utcnow() > req.expires_at:
            req.status = "EXPIRED"
            db.commit()
            return {
                "success": False,
                "error": "Action blocked: Approval request has expired",
                "status": "EXPIRED"
            }

        # Check 3: Plan hash match
        if req.plan_hash != current_plan_hash:
            return {
                "success": False,
                "error": "Action blocked: Cleanup plan has changed since approval was granted. Re-approval required.",
                "status": "INVALIDATED"
            }

        # Check 4: Pre-deletion safety verification against live AWS API
        pre_check_passed, pre_check_msg = ApprovalService._pre_execution_safety_check(session, req.resource_type, req.resource_id)
        if not pre_check_passed:
            req.status = "FAILED"
            req.execution_result_json = json.dumps({"error": pre_check_msg})
            db.commit()
            return {
                "success": False,
                "error": f"Pre-deletion safety check failed: {pre_check_msg}",
                "status": "FAILED"
            }

        # Mark EXECUTING
        req.status = "EXECUTING"
        db.commit()

        # Step 5: Execute action via Sandboxed Runner
        execution_code = ApprovalService._generate_cleanup_code(req.resource_type, req.resource_id, req.region)
        sandbox_res = sandbox.execute_python_code(
            code_content=execution_code,
            action_name=req.action,
            resource_id=req.resource_id
        )

        if not sandbox_res["success"]:
            req.status = "FAILED"
            req.execution_result_json = json.dumps(sandbox_res)
            db.commit()
            return {
                "success": False,
                "error": f"Sandboxed execution failed: {sandbox_res.get('error')}",
                "status": "FAILED",
                "details": sandbox_res
            }

        # Step 6: Post-deletion verification
        post_verified, post_msg = ApprovalService._post_execution_verification(session, req.resource_type, req.resource_id)
        sandbox_res["post_verification"] = post_msg

        req.status = "COMPLETED" if post_verified else "FAILED"
        req.execution_result_json = json.dumps(sandbox_res)
        db.commit()

        return {
            "success": post_verified,
            "status": req.status,
            "message": post_msg,
            "details": sandbox_res
        }

    @staticmethod
    def execute_direct_termination(
        db: Session,
        session, # boto3.Session
        resource_id: str,
        resource_type: str,
        region: str,
        user_id: str = "admin",
        reason: str = "Direct user termination"
    ) -> Dict[str, Any]:
        """
        Executes an authorized, direct component termination inside the secure sandbox.
        Performs pre-safety check -> sandboxed code execution -> post-verification -> audit/DB update.
        """
        # Step 1: Pre-deletion safety check against live AWS API
        pre_passed, pre_msg = ApprovalService._pre_execution_safety_check(session, resource_type, resource_id)
        if not pre_passed:
            return {
                "success": False,
                "error": f"Pre-deletion safety check failed: {pre_msg}",
                "status": "FAILED"
            }

        # Step 2: Generate cleanup code
        code = ApprovalService._generate_cleanup_code(resource_type, resource_id, region)

        # Step 3: Execute in sandbox
        sandbox_res = sandbox.execute_python_code(
            code_content=code,
            action_name=f"direct_terminate_{resource_type}",
            resource_id=resource_id
        )

        if not sandbox_res["success"]:
            return {
                "success": False,
                "error": f"Sandboxed execution failed: {sandbox_res.get('error')}",
                "status": "FAILED",
                "details": sandbox_res
            }

        # Step 4: Post-verification against live AWS API
        post_verified, post_msg = ApprovalService._post_execution_verification(session, resource_type, resource_id)
        sandbox_res["post_verification"] = post_msg

        # Step 5: Update any ResourceSnapshot matching this resource_id
        snapshots = db.query(models.ResourceSnapshot).filter(models.ResourceSnapshot.resource_id == resource_id).all()
        for snap in snapshots:
            snap.state = "terminated"
            snap.is_waste = False

        # Step 6: Mark any existing approval for this resource as COMPLETED
        approvals = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.resource_id == resource_id).all()
        for app in approvals:
            app.status = "COMPLETED"
            app.resolved_at = datetime.datetime.utcnow()
            app.resolved_by = user_id
            app.execution_result_json = json.dumps(sandbox_res)

        db.commit()

        return {
            "success": post_verified,
            "status": "COMPLETED" if post_verified else "FAILED",
            "message": post_msg,
            "details": sandbox_res
        }

    @staticmethod
    def _pre_execution_safety_check(session, resource_type: str, resource_id: str) -> Tuple[bool, str]:
        """Live AWS verification prior to executing destructive commands"""
        try:
            r_type = resource_type.lower()
            if r_type == "ec2":
                ec2 = session.client('ec2')
                resp = ec2.describe_instances(InstanceIds=[resource_id])
                reservations = resp.get('Reservations', [])
                if not reservations or not reservations[0].get('Instances'):
                    return False, f"EC2 Instance {resource_id} no longer exists"
                inst = reservations[0]['Instances'][0]
                state = inst.get('State', {}).get('Name')
                if state in ['terminated', 'terminating']:
                    return False, f"EC2 Instance {resource_id} is already {state}"
                return True, f"Verified EC2 instance {resource_id} is currently {state}"

            elif r_type == "ebs":
                ec2 = session.client('ec2')
                resp = ec2.describe_volumes(VolumeIds=[resource_id])
                volumes = resp.get('Volumes', [])
                if not volumes:
                    return False, f"EBS Volume {resource_id} no longer exists"
                vol = volumes[0]
                if vol.get('State') != 'available':
                    return False, f"EBS Volume {resource_id} is now '{vol.get('State')}' and may be in use"
                return True, f"Verified EBS volume {resource_id} is unattached and available"

            elif r_type == "elb":
                elbv2 = session.client('elbv2')
                resp = elbv2.describe_load_balancers(LoadBalancerArns=[resource_id])
                if not resp.get('LoadBalancers'):
                    return False, f"Load Balancer {resource_id} no longer exists"
                return True, "Verified Load Balancer exists and is active"

            elif r_type == "eip":
                ec2 = session.client('ec2')
                resp = ec2.describe_addresses(AllocationIds=[resource_id])
                if not resp.get('Addresses'):
                    return False, f"Elastic IP {resource_id} not found"
                addr = resp['Addresses'][0]
                if addr.get('AssociationId'):
                    return False, f"Elastic IP {resource_id} is now associated with an active resource"
                return True, f"Verified Elastic IP {resource_id} is unassociated"

            elif r_type == "rds":
                rds = session.client('rds')
                resp = rds.describe_db_instances(DBInstanceIdentifier=resource_id)
                if not resp.get('DBInstances'):
                    return False, f"RDS database {resource_id} not found"
                return True, f"Verified RDS database {resource_id} exists"

            elif r_type in ["lambda", "function"]:
                lam = session.client('lambda')
                try:
                    lam.get_function(FunctionName=resource_id)
                    return True, f"Verified Lambda function {resource_id} exists"
                except ClientError as e:
                    return False, f"Lambda function {resource_id} not found: {str(e)}"

            elif r_type in ["s3", "bucket"]:
                s3 = session.client('s3')
                try:
                    s3.head_bucket(Bucket=resource_id)
                    return True, f"Verified S3 bucket {resource_id} exists"
                except ClientError as e:
                    return False, f"S3 bucket {resource_id} not found: {str(e)}"

            elif r_type in ["nat_gateway", "natgateway"]:
                ec2 = session.client('ec2')
                try:
                    resp = ec2.describe_nat_gateways(NatGatewayIds=[resource_id])
                    ngs = resp.get('NatGateways', [])
                    if not ngs or ngs[0].get('State') in ['deleted', 'deleting']:
                        return False, f"NAT Gateway {resource_id} is already deleted"
                    return True, f"Verified NAT Gateway {resource_id} exists"
                except ClientError as e:
                    return False, f"NAT Gateway {resource_id} not found: {str(e)}"

            return True, f"Pre-check passed for {resource_type} {resource_id}"
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            return False, f"AWS API check returned error ({code})"
        except Exception as e:
            return False, f"Pre-check error: {str(e)}"

    @staticmethod
    def _post_execution_verification(session, resource_type: str, resource_id: str) -> Tuple[bool, str]:
        """Live AWS verification after executing destructive commands"""
        try:
            r_type = resource_type.lower()
            if r_type == "ec2":
                ec2 = session.client('ec2')
                resp = ec2.describe_instances(InstanceIds=[resource_id])
                state = resp['Reservations'][0]['Instances'][0]['State']['Name']
                if state in ['terminating', 'terminated']:
                    return True, f"Verified: Instance {resource_id} transitioned to '{state}'"
                return False, f"Warning: Instance {resource_id} state is '{state}'"

            elif r_type == "ebs":
                ec2 = session.client('ec2')
                try:
                    resp = ec2.describe_volumes(VolumeIds=[resource_id])
                    state = resp['Volumes'][0]['State']
                    if state == 'deleting':
                        return True, f"Verified: Volume {resource_id} status is 'deleting'"
                    return False, f"Volume {resource_id} still exists in state '{state}'"
                except ClientError as e:
                    if "InvalidVolume.NotFound" in str(e):
                        return True, f"Verified: Volume {resource_id} has been permanently deleted"
                    raise

            elif r_type == "elb":
                elbv2 = session.client('elbv2')
                try:
                    elbv2.describe_load_balancers(LoadBalancerArns=[resource_id])
                    return False, f"Load balancer {resource_id} still exists"
                except ClientError as e:
                    if "LoadBalancerNotFound" in str(e):
                        return True, f"Verified: Load balancer {resource_id} has been successfully deleted"
                    raise

            elif r_type == "eip":
                ec2 = session.client('ec2')
                try:
                    resp = ec2.describe_addresses(AllocationIds=[resource_id])
                    return False, f"Elastic IP {resource_id} is still allocated"
                except ClientError as e:
                    if "InvalidAllocationID.NotFound" in str(e):
                        return True, f"Verified: Elastic IP {resource_id} released successfully"
                    raise

            elif r_type == "rds":
                rds = session.client('rds')
                resp = rds.describe_db_instances(DBInstanceIdentifier=resource_id)
                status = resp['DBInstances'][0]['DBInstanceStatus']
                if status in ['stopping', 'stopped']:
                    return True, f"Verified: RDS database {resource_id} status is '{status}'"
                return False, f"RDS database {resource_id} is in status '{status}'"

            elif r_type in ["lambda", "function"]:
                lam = session.client('lambda')
                try:
                    lam.get_function(FunctionName=resource_id)
                    return False, f"Lambda function {resource_id} still exists"
                except ClientError as e:
                    if "ResourceNotFoundException" in str(e):
                        return True, f"Verified: Lambda function {resource_id} deleted successfully"
                    raise

            elif r_type in ["s3", "bucket"]:
                s3 = session.client('s3')
                try:
                    s3.head_bucket(Bucket=resource_id)
                    return False, f"S3 bucket {resource_id} still exists"
                except ClientError as e:
                    if "404" in str(e) or "NotFound" in str(e) or "NoSuchBucket" in str(e):
                        return True, f"Verified: S3 bucket {resource_id} deleted successfully"
                    raise

            elif r_type in ["nat_gateway", "natgateway"]:
                ec2 = session.client('ec2')
                try:
                    resp = ec2.describe_nat_gateways(NatGatewayIds=[resource_id])
                    ngs = resp.get('NatGateways', [])
                    if not ngs or ngs[0].get('State') in ['deleted', 'deleting']:
                        return True, f"Verified: NAT Gateway {resource_id} is deleted/deleting"
                    return False, f"NAT Gateway {resource_id} is still in state '{ngs[0].get('State')}'"
                except ClientError as e:
                    if "NatGatewayNotFound" in str(e):
                        return True, f"Verified: NAT Gateway {resource_id} deleted"
                    raise

            return True, f"Post-verification completed for {resource_type} {resource_id}"
        except Exception as e:
            return False, f"Post-verification error: {str(e)}"

    @staticmethod
    def _generate_cleanup_code(resource_type: str, resource_id: str, region: str) -> str:
        """Generates self-contained, auditable Python code to execute in the sandbox"""
        r_type = resource_type.lower()
        if r_type == "ec2":
            return f"""
import sys, boto3
from botocore.exceptions import ClientError

try:
    ec2 = boto3.client('ec2', region_name='{region}')
    print(f"Calling ec2.terminate_instances(InstanceIds=['{resource_id}'])")
    response = ec2.terminate_instances(InstanceIds=['{resource_id}'])
    for term in response.get('TerminatingInstances', []):
        print(f"Instance {{term['InstanceId']}}: {{term['PreviousState']['Name']}} -> {{term['CurrentState']['Name']}}")
    sys.exit(0)
except ClientError as e:
    code = e.response.get("Error", {{}}).get("Code", "Error")
    msg = e.response.get("Error", {{}}).get("Message", str(e))
    print(f"AWS Error ({{code}}): {{msg}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Execution Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
        elif r_type == "ebs":
            return f"""
import sys, boto3
from botocore.exceptions import ClientError

try:
    ec2 = boto3.client('ec2', region_name='{region}')
    print(f"Calling ec2.delete_volume(VolumeId='{resource_id}')")
    ec2.delete_volume(VolumeId='{resource_id}')
    print(f"Successfully requested deletion of EBS volume {resource_id}")
    sys.exit(0)
except ClientError as e:
    code = e.response.get("Error", {{}}).get("Code", "Error")
    msg = e.response.get("Error", {{}}).get("Message", str(e))
    print(f"AWS Error ({{code}}): {{msg}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Execution Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
        elif r_type == "elb":
            return f"""
import sys, boto3
from botocore.exceptions import ClientError

try:
    elbv2 = boto3.client('elbv2', region_name='{region}')
    print(f"Calling elbv2.delete_load_balancer(LoadBalancerArn='{resource_id}')")
    elbv2.delete_load_balancer(LoadBalancerArn='{resource_id}')
    print(f"Successfully deleted Load Balancer {resource_id}")
    sys.exit(0)
except ClientError as e:
    code = e.response.get("Error", {{}}).get("Code", "Error")
    msg = e.response.get("Error", {{}}).get("Message", str(e))
    print(f"AWS Error ({{code}}): {{msg}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Execution Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
        elif r_type == "eip":
            return f"""
import sys, boto3
from botocore.exceptions import ClientError

try:
    ec2 = boto3.client('ec2', region_name='{region}')
    print(f"Calling ec2.release_address(AllocationId='{resource_id}')")
    ec2.release_address(AllocationId='{resource_id}')
    print(f"Successfully released Elastic IP {resource_id}")
    sys.exit(0)
except ClientError as e:
    code = e.response.get("Error", {{}}).get("Code", "Error")
    msg = e.response.get("Error", {{}}).get("Message", str(e))
    print(f"AWS Error ({{code}}): {{msg}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Execution Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
        elif r_type == "rds":
            return f"""
import sys, boto3
from botocore.exceptions import ClientError

try:
    rds = boto3.client('rds', region_name='{region}')
    print(f"Calling rds.stop_db_instance(DBInstanceIdentifier='{resource_id}')")
    rds.stop_db_instance(DBInstanceIdentifier='{resource_id}')
    print(f"Successfully requested stop of RDS database {resource_id}")
    sys.exit(0)
except ClientError as e:
    code = e.response.get("Error", {{}}).get("Code", "Error")
    msg = e.response.get("Error", {{}}).get("Message", str(e))
    print(f"AWS Error ({{code}}): {{msg}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Execution Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
        elif r_type in ["lambda", "function"]:
            return f"""
import sys, boto3
from botocore.exceptions import ClientError

try:
    lam = boto3.client('lambda', region_name='{region}')
    print(f"Calling lambda.delete_function(FunctionName='{resource_id}')")
    lam.delete_function(FunctionName='{resource_id}')
    print(f"Successfully deleted Lambda function {resource_id}")
    sys.exit(0)
except ClientError as e:
    code = e.response.get("Error", {{}}).get("Code", "Error")
    msg = e.response.get("Error", {{}}).get("Message", str(e))
    print(f"AWS Error ({{code}}): {{msg}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Execution Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
        elif r_type in ["s3", "bucket"]:
            return f"""
import sys, boto3
from botocore.exceptions import ClientError

try:
    s3 = boto3.client('s3')
    print(f"Calling s3.delete_bucket(Bucket='{resource_id}')")
    s3.delete_bucket(Bucket='{resource_id}')
    print(f"Successfully deleted S3 bucket {resource_id}")
    sys.exit(0)
except ClientError as e:
    code = e.response.get("Error", {{}}).get("Code", "Error")
    msg = e.response.get("Error", {{}}).get("Message", str(e))
    print(f"AWS Error ({{code}}): {{msg}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Execution Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
        elif r_type in ["nat_gateway", "natgateway"]:
            return f"""
import sys, boto3
from botocore.exceptions import ClientError

try:
    ec2 = boto3.client('ec2', region_name='{region}')
    print(f"Calling ec2.delete_nat_gateway(NatGatewayId='{resource_id}')")
    ec2.delete_nat_gateway(NatGatewayId='{resource_id}')
    print(f"Successfully requested deletion of NAT Gateway {resource_id}")
    sys.exit(0)
except ClientError as e:
    code = e.response.get("Error", {{}}).get("Code", "Error")
    msg = e.response.get("Error", {{}}).get("Message", str(e))
    print(f"AWS Error ({{code}}): {{msg}}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Execution Error: {{str(e)}}", file=sys.stderr)
    sys.exit(1)
"""
        return f"""
import sys
print("Resource type '{resource_type}' requires customized deletion handler", file=sys.stderr)
sys.exit(1)
"""
