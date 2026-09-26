import asyncio
import datetime
import json
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from . import models, schemas
from .aws_session import resolve_aws_session
from .cost_engine import CompositeCostEstimator
from .analyzers.ec2_analyzer import IdleEC2Analyzer
from .analyzers.ebs_analyzer import OrphanedEBSAnalyzer
from .analyzers.elb_analyzer import UnusedLoadBalancerAnalyzer
from .analyzers.elastic_ip_analyzer import UnattachedElasticIPAnalyzer
from .analyzers.nat_gateway_analyzer import IdleNATGatewayAnalyzer
from .analyzers.rds_analyzer import RDSAnalyzer
from .analyzers.s3_analyzer import S3BucketAnalyzer
from .analyzers.lambda_analyzer import LambdaAnalyzer
from .analyzers.global_resource_scanner import GlobalResourceScanner
from .approval_service import ApprovalService, compute_plan_hash
from .notification_service import NotificationService, ws_manager
from .audit_service import AuditService

class CloudJanitorAgent:
    """
    Autonomous AWS Cloud Cost Cleanup Agent.
    Executes the structured lifecycle:
    DISCOVER -> OBSERVE -> ANALYZE -> ESTIMATE COST -> IDENTIFY CANDIDATES -> GENERATE CLEANUP PLAN -> RISK ANALYSIS -> STOP AT HUMAN APPROVAL
    """
    def __init__(self, db: Session):
        self.db = db

    async def _emit_event(self, run_id: str, stage: str, message: str, level: str = "info", data: Optional[Dict[str, Any]] = None):
        """Emits an event simultaneously to WebSocket clients and audit trail"""
        event_payload = {
            "type": "agent_activity",
            "run_id": run_id,
            "stage": stage,
            "message": message,
            "level": level,
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "data": data or {}
        }
        await ws_manager.broadcast(event_payload)

    async def run_discovery_and_planning(
        self,
        prompt: str,
        user_id: str = "admin",
        mode: str = "READ_ONLY",
        region_override: Optional[str] = None
    ) -> models.AgentRun:
        start_time = time.time()
        
        # 1. Initialize AgentRun
        run = models.AgentRun(
            prompt=prompt,
            status="STARTING",
            mode=mode,
            created_at=datetime.datetime.utcnow()
        )
        self.db.add(run)
        self.db.commit()
        run_id = run.id

        AuditService.record_event(
            self.db, action="AGENT_STARTED", status="SUCCESS",
            run_id=run_id, user=user_id, reason=f"Triggered by prompt: '{prompt}'"
        )
        await self._emit_event(run_id, "STARTING", f"Agent initialized with prompt: '{prompt}'")

        # 2. Connect to AWS
        await self._emit_event(run_id, "CONNECTING", "Resolving AWS credentials and verifying identity via STS...")
        session, auth_meta = resolve_aws_session(self.db, explicit_region=region_override)
        
        if not auth_meta["is_authenticated"]:
            run.status = "FAILED"
            run.summary = f"Authentication Failed: {auth_meta['error']}"
            self.db.commit()
            
            AuditService.record_event(
                self.db, action="AWS_CONNECTED", status="FAILED",
                run_id=run_id, user=user_id, reason=auth_meta['error']
            )
            await self._emit_event(run_id, "FAILED", f"AWS Authentication failed: {auth_meta['error']}", level="error")
            return run

        account_id = auth_meta["account_id"]
        region = auth_meta["region"]
        run.aws_account_id = account_id
        run.region = region
        self.db.commit()

        AuditService.record_event(
            self.db, action="AWS_CONNECTED", status="SUCCESS",
            run_id=run_id, user=user_id, aws_account_id=account_id, region=region,
            reason=f"Authenticated as ARN: {auth_meta['arn']} via {auth_meta['auth_source']}"
        )
        await self._emit_event(
            run_id, "AUTHENTICATED",
            f"Connected to AWS Account {account_id} in {region} via {auth_meta['auth_source']}",
            data={"account_id": account_id, "arn": auth_meta["arn"], "region": region}
        )

        # 3. Discovery & Analysis
        run.status = "DISCOVERING"
        self.db.commit()
        AuditService.record_event(self.db, action="DISCOVERY_STARTED", status="SUCCESS", run_id=run_id, aws_account_id=account_id, region=region)

        cost_estimator = CompositeCostEstimator(session)
        all_candidates: List[Dict[str, Any]] = []

        # Step 3a: EC2
        await self._emit_event(run_id, "DISCOVERING", "Scanning EC2 compute instances and querying CloudWatch CPU metrics...")
        ec2_analyzer = IdleEC2Analyzer(session, cost_estimator)
        ec2_candidates = ec2_analyzer.analyze_instances()
        all_candidates.extend(ec2_candidates)
        await self._emit_event(
            run_id, "DISCOVERING",
            f"Discovered {len(ec2_candidates)} EC2 instances ({sum(1 for c in ec2_candidates if c['is_waste'])} waste candidates)"
        )

        # Step 3b: EBS
        await self._emit_event(run_id, "DISCOVERING", "Scanning EBS storage volumes for unattached/orphaned disks...")
        ebs_analyzer = OrphanedEBSAnalyzer(session, cost_estimator)
        ebs_candidates = ebs_analyzer.analyze_volumes()
        all_candidates.extend(ebs_candidates)
        await self._emit_event(
            run_id, "DISCOVERING",
            f"Discovered {len(ebs_candidates)} EBS volumes ({sum(1 for c in ebs_candidates if c['is_waste'])} unattached/orphaned)"
        )

        # Step 3c: ELB
        await self._emit_event(run_id, "DISCOVERING", "Scanning Application and Network Load Balancers for inactive target routing...")
        elb_analyzer = UnusedLoadBalancerAnalyzer(session, cost_estimator)
        elb_candidates = elb_analyzer.analyze_load_balancers()
        all_candidates.extend(elb_candidates)
        await self._emit_event(
            run_id, "DISCOVERING",
            f"Discovered {len(elb_candidates)} Load Balancers ({sum(1 for c in elb_candidates if c['is_waste'])} unused)"
        )

        # Step 3d: Elastic IPs
        await self._emit_event(run_id, "DISCOVERING", "Scanning Elastic IP addresses for idle unassociated allocations...")
        eip_analyzer = UnattachedElasticIPAnalyzer(session, cost_estimator)
        eip_candidates = eip_analyzer.analyze_eips()
        all_candidates.extend(eip_candidates)
        await self._emit_event(
            run_id, "DISCOVERING",
            f"Discovered {len(eip_candidates)} Elastic IPs ({sum(1 for c in eip_candidates if c['is_waste'])} unattached)"
        )

        # Step 3e: NAT Gateways
        await self._emit_event(run_id, "DISCOVERING", "Scanning VPC NAT Gateways for base provisioning costs...")
        nat_analyzer = IdleNATGatewayAnalyzer(session, cost_estimator)
        nat_candidates = nat_analyzer.analyze_nat_gateways()
        all_candidates.extend(nat_candidates)

        # Step 3f: RDS
        await self._emit_event(run_id, "DISCOVERING", "Scanning RDS database instances and clusters...")
        rds_analyzer = RDSAnalyzer(session, cost_estimator)
        rds_candidates = rds_analyzer.analyze_databases()
        all_candidates.extend(rds_candidates)

        # Step 3g: S3
        await self._emit_event(run_id, "DISCOVERING", "Auditing Amazon S3 storage buckets...")
        s3_analyzer = S3BucketAnalyzer(session, cost_estimator)
        s3_candidates = s3_analyzer.analyze_buckets()
        all_candidates.extend(s3_candidates)

        # Step 3h: Lambda
        await self._emit_event(run_id, "DISCOVERING", "Auditing AWS Lambda serverless functions...")
        lambda_analyzer = LambdaAnalyzer(session, cost_estimator)
        lambda_candidates = lambda_analyzer.analyze_functions()
        all_candidates.extend(lambda_candidates)

        # Step 3i: Elastic Global AWS Scanner (Find ANY other running AWS service!)
        await self._emit_event(run_id, "DISCOVERING", "Elastic Global Scan: Searching entire AWS account for any other active services...")
        discovered_ids = {c["resource_id"] for c in all_candidates}
        global_scanner = GlobalResourceScanner(session, cost_estimator)
        global_candidates = global_scanner.scan_all_services(already_discovered_ids=discovered_ids)
        if global_candidates:
            all_candidates.extend(global_candidates)
            await self._emit_event(
                run_id, "DISCOVERING",
                f"Elastic Global Scan identified {len(global_candidates)} additional active AWS resources across account services"
            )

        # 4. Save Resource Snapshots
        waste_candidates = [c for c in all_candidates if c.get("is_waste")]
        total_monthly_savings = round(sum(c.get("monthly_cost", 0.0) for c in waste_candidates), 2)
        total_annual_savings = round(total_monthly_savings * 12, 2)

        for c in all_candidates:
            snap = models.ResourceSnapshot(
                run_id=run_id,
                resource_id=c["resource_id"],
                resource_type=c["resource_type"],
                region=c["region"],
                name=c["name"],
                state=c["state"],
                instance_type_or_size=c.get("instance_type_or_size"),
                monthly_cost=c.get("monthly_cost", 0.0),
                cost_source=c.get("cost_source", "calculated_estimate"),
                is_waste=c.get("is_waste", False),
                confidence=c.get("confidence", 0.0),
                waste_finding=c.get("waste_finding"),
                evidence_json=json.dumps(c.get("evidence", [])),
                recommended_action=c.get("recommended_action", "retain"),
                requires_approval=c.get("requires_approval", False)
            )
            self.db.add(snap)

        run.total_resources_scanned = len(all_candidates)
        run.waste_candidates_count = len(waste_candidates)
        run.potential_monthly_savings = total_monthly_savings
        self.db.commit()

        AuditService.record_event(
            self.db, action="CANDIDATE_IDENTIFIED", status="SUCCESS",
            run_id=run_id, aws_account_id=account_id, region=region,
            reason=f"Identified {len(waste_candidates)} cleanup candidates with ${total_monthly_savings}/mo potential savings"
        )
        await self._emit_event(
            run_id, "ANALYZING",
            f"Identified {len(waste_candidates)} waste candidates out of {len(all_candidates)} total resources. Potential savings: ${total_monthly_savings}/mo",
            data={"waste_count": len(waste_candidates), "total_count": len(all_candidates), "monthly_savings": total_monthly_savings}
        )

        # 5. Generate Cleanup Plan & Plan Hash
        plan_hash = compute_plan_hash(all_candidates, account_id, region)
        plan = models.CleanupPlan(
            run_id=run_id,
            aws_account_id=account_id,
            region=region,
            plan_version=1,
            plan_hash=plan_hash,
            status="PENDING_APPROVAL" if waste_candidates else "COMPLETED",
            candidates_count=len(waste_candidates),
            total_monthly_savings=total_monthly_savings,
            total_annual_savings=total_annual_savings,
            risk_summary=f"Plan contains {len(waste_candidates)} proposed destructive actions requiring human review."
        )
        self.db.add(plan)
        self.db.commit()

        AuditService.record_event(
            self.db, action="PLAN_GENERATED", status="SUCCESS",
            run_id=run_id, aws_account_id=account_id, region=region,
            reason=f"Generated cleanup plan {plan.id} (hash: {plan_hash[:8]}...)"
        )
        await self._emit_event(
            run_id, "PLAN_GENERATED",
            f"Generated cleanup plan {plan.id} (Plan Hash: {plan_hash[:12]}...)",
            data={"plan_id": plan.id, "plan_hash": plan_hash}
        )

        # 6. STOP BEFORE IRREVERSIBLE ACTION: Human Approval Checkpoint
        approval_candidates = [c for c in waste_candidates if c.get("requires_approval")]
        if approval_candidates:
            run.status = "WAITING_APPROVAL"
            self.db.commit()

            # Create individual ApprovalRequest records
            approvals = ApprovalService.create_approval_requests(
                db=self.db,
                run_id=run_id,
                plan_id=plan.id,
                aws_account_id=account_id,
                region=region,
                plan_hash=plan_hash,
                candidates=approval_candidates
            )

            AuditService.record_event(
                self.db, action="APPROVAL_REQUESTED", status="PENDING",
                run_id=run_id, aws_account_id=account_id, region=region,
                reason=f"Created {len(approvals)} approval requests for destructive cleanup"
            )

            # Dispatch notification
            notif_msg = f"{len(approvals)} destructive actions require your approval. Potential monthly savings: ${total_monthly_savings:.2f}/mo."
            NotificationService.record_and_dispatch_notification(
                db=self.db,
                notif_type="approval_required",
                title="CloudJanitor Needs Your Approval",
                message=notif_msg,
                link="/approvals",
                approval_id=approvals[0].id if approvals else None,
                session=session
            )

            await self._emit_event(
                run_id, "WAITING_APPROVAL",
                f"⏸ HUMAN APPROVAL REQUIRED: {len(approvals)} destructive actions paused at gate. Potential savings: ${total_monthly_savings:.2f}/month",
                level="warning",
                data={"approval_count": len(approvals), "plan_id": plan.id, "monthly_savings": total_monthly_savings}
            )
        else:
            run.status = "COMPLETED"
            run.completed_at = datetime.datetime.utcnow()
            run.summary = "Scan completed. No high-confidence waste candidates requiring destructive cleanup were detected."
            self.db.commit()

            await self._emit_event(
                run_id, "COMPLETED",
                "Scan complete. No destructive actions needed. All resources are currently optimized.",
                level="success"
            )

        return run
