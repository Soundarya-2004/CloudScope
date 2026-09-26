import json
import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from . import schemas, database, models, crypto, auth
from .aws_session import resolve_aws_session, check_aws_permissions
from .agent_loop import CloudJanitorAgent
from .approval_service import ApprovalService
from .notification_service import ws_manager, NotificationService
from .audit_service import AuditService
from .cost_engine import CompositeCostEstimator
from .agent_llm import truefoundry_client

router = APIRouter(prefix="/api")

# ==========================================
# WEBSOCKET STREAMING
# ==========================================
@router.websocket("/ws/agent")
async def websocket_agent_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive & handle incoming pings
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# ==========================================
# AUTH & AWS IDENTITY
# ==========================================
@router.post("/auth/aws-login")
def aws_login(request: schemas.AWSConnectRequest, db: Session = Depends(database.get_db)):
    """Logs in using AWS credentials, verifies via STS, and issues JWT"""
    session, meta = resolve_aws_session(
        db=None,
        explicit_key=request.aws_access_key,
        explicit_secret=request.aws_secret_key,
        explicit_region=request.aws_region
    )
    if not meta["is_authenticated"]:
        raise HTTPException(status_code=401, detail=meta["error"] or "Invalid AWS Credentials")

    # Persist encrypted
    db_config = db.query(models.UserSetting).first()
    encrypted_secret = crypto.encrypt(request.aws_secret_key) if request.aws_secret_key else None
    
    if not db_config:
        db_config = models.UserSetting(
            aws_access_key=request.aws_access_key,
            aws_secret_key=encrypted_secret,
            aws_region=request.aws_region,
            aws_account_id=meta["account_id"],
            aws_arn=meta["arn"],
            auth_mode=request.auth_mode,
            is_configured=True
        )
        db.add(db_config)
    else:
        if request.aws_access_key:
            db_config.aws_access_key = request.aws_access_key
        if encrypted_secret:
            db_config.aws_secret_key = encrypted_secret
        db_config.aws_region = request.aws_region
        db_config.aws_account_id = meta["account_id"]
        db_config.aws_arn = meta["arn"]
        db_config.is_configured = True
    db.commit()

    access_token = auth.create_access_token(data={"sub": "aws-admin", "role": "Admin"})
    return {"access_token": access_token, "token_type": "bearer", "metadata": meta}

@router.get("/auth/me", response_model=schemas.UserResponse)
def read_current_user(current_user: models.User = Depends(auth.get_current_user)):
    return schemas.UserResponse(username=current_user.username, role=current_user.role)

@router.get("/aws/identity", response_model=schemas.AWSIdentityResponse)
def get_aws_identity(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    session, meta = resolve_aws_session(db)
    user_setting = db.query(models.UserSetting).first()
    agent_mode = user_setting.agent_mode if user_setting else "READ_ONLY"

    if not meta["is_authenticated"]:
        return schemas.AWSIdentityResponse(
            account_id="Not Connected",
            arn="Not Connected",
            user_id="None",
            region=meta["region"],
            auth_mode=meta["auth_source"],
            agent_mode=agent_mode,
            is_authenticated=False,
            read_permissions_valid=False,
            destructive_permissions_valid=False,
            warning=meta.get("error")
        )

    # Check two-phase permissions
    perm_checks = check_aws_permissions(session)
    read_ok = len(perm_checks["missing_read_permissions"]) == 0

    return schemas.AWSIdentityResponse(
        account_id=meta["account_id"] or "Unknown",
        arn=meta["arn"] or "Unknown",
        user_id=meta["user_id"] or "Unknown",
        region=meta["region"],
        auth_mode=meta["auth_source"],
        agent_mode=agent_mode,
        is_authenticated=True,
        read_permissions_valid=read_ok,
        destructive_permissions_valid=(agent_mode == "ACTION"),
        warning="; ".join(perm_checks["warnings"]) if perm_checks["warnings"] else None
    )

@router.post("/aws/mode")
def toggle_agent_mode(req: schemas.AgentModeToggleRequest, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Toggles between READ_ONLY and ACTION mode. ACTION mode requires explicit confirmation."""
    if req.mode == "ACTION" and not req.confirmation:
        raise HTTPException(status_code=400, detail="Enabling ACTION mode requires explicit confirmation checkbox.")

    setting = db.query(models.UserSetting).first()
    if not setting:
        setting = models.UserSetting(agent_mode=req.mode)
        db.add(setting)
    else:
        setting.agent_mode = req.mode
    db.commit()

    AuditService.record_event(
        db, action="AGENT_MODE_CHANGED", status="SUCCESS",
        user=current_user.username, reason=f"Mode toggled to {req.mode}"
    )
    return {"mode": req.mode, "status": "updated"}

# ==========================================
# AGENT RUNS & NATURAL LANGUAGE REASONING
# ==========================================
@router.post("/agent/run", response_model=schemas.AgentRunResponse)
async def start_agent_run(req: schemas.AgentRunRequest, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    setting = db.query(models.UserSetting).first()
    current_mode = req.mode or (setting.agent_mode if setting else "READ_ONLY")
    agent = CloudJanitorAgent(db)
    
    run = await agent.run_discovery_and_planning(
        prompt=req.prompt,
        user_id=current_user.username,
        mode=current_mode,
        region_override=req.region
    )
    return schemas.AgentRunResponse(
        id=run.id,
        prompt=run.prompt,
        status=run.status,
        mode=run.mode,
        aws_account_id=run.aws_account_id,
        region=run.region,
        total_resources_scanned=run.total_resources_scanned,
        waste_candidates_count=run.waste_candidates_count,
        potential_monthly_savings=run.potential_monthly_savings,
        summary=run.summary,
        created_at=run.created_at,
        completed_at=run.completed_at
    )

@router.get("/agent/runs", response_model=List[schemas.AgentRunResponse])
def list_agent_runs(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    runs = db.query(models.AgentRun).order_by(models.AgentRun.created_at.desc()).limit(20).all()
    return [
        schemas.AgentRunResponse(
            id=r.id, prompt=r.prompt, status=r.status, mode=r.mode,
            aws_account_id=r.aws_account_id, region=r.region,
            total_resources_scanned=r.total_resources_scanned,
            waste_candidates_count=r.waste_candidates_count,
            potential_monthly_savings=r.potential_monthly_savings,
            summary=r.summary, created_at=r.created_at, completed_at=r.completed_at
        ) for r in runs
    ]

@router.get("/agent/runs/{run_id}")
def get_agent_run_detail(run_id: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    run = db.query(models.AgentRun).filter(models.AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
        
    snapshots = db.query(models.ResourceSnapshot).filter(models.ResourceSnapshot.run_id == run_id).all()
    plan = db.query(models.CleanupPlan).filter(models.CleanupPlan.run_id == run_id).first()
    approvals = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.run_id == run_id).all()

    return {
        "run": {
            "id": run.id, "prompt": run.prompt, "status": run.status, "mode": run.mode,
            "aws_account_id": run.aws_account_id, "region": run.region,
            "total_resources_scanned": run.total_resources_scanned,
            "waste_candidates_count": run.waste_candidates_count,
            "potential_monthly_savings": run.potential_monthly_savings,
            "created_at": run.created_at
        },
        "plan": {
            "id": plan.id, "plan_hash": plan.plan_hash, "status": plan.status,
            "candidates_count": plan.candidates_count, "total_monthly_savings": plan.total_monthly_savings
        } if plan else None,
        "candidates": [
            {
                "resource_id": s.resource_id, "resource_type": s.resource_type, "region": s.region,
                "name": s.name, "state": s.state, "monthly_cost": s.monthly_cost,
                "is_waste": s.is_waste, "confidence": s.confidence, "waste_finding": s.waste_finding,
                "evidence": json.loads(s.evidence_json or "[]"),
                "recommended_action": s.recommended_action, "requires_approval": s.requires_approval
            } for s in snapshots
        ],
        "approvals": [
            {
                "id": a.id, "resource_id": a.resource_id, "resource_type": a.resource_type,
                "resource_name": a.resource_name, "action": a.action, "risk_level": a.risk_level,
                "estimated_monthly_savings": a.estimated_monthly_savings, "status": a.status,
                "expires_at": a.expires_at
            } for a in approvals
        ]
    }

@router.post("/agent/ask")
async def ask_agent_reasoning(req: Dict[str, Any], db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Natural Language reasoning explanation powered by TrueFoundry AI Gateway (Polaris)"""
    resource_id = req.get("resource_id")
    question = req.get("question")
    
    snapshot = db.query(models.ResourceSnapshot).filter(models.ResourceSnapshot.resource_id == resource_id).order_by(models.ResourceSnapshot.scanned_at.desc()).first()
    res_dict = {}
    if snapshot:
        res_dict = {
            "resource_id": snapshot.resource_id,
            "resource_type": snapshot.resource_type,
            "name": snapshot.name,
            "state": snapshot.state,
            "monthly_cost": snapshot.monthly_cost,
            "confidence": snapshot.confidence,
            "waste_finding": snapshot.waste_finding,
            "evidence": json.loads(snapshot.evidence_json or "[]"),
            "recommended_action": snapshot.recommended_action
        }
    else:
        res_dict = {"resource_id": resource_id, "evidence": ["Resource observed in live infrastructure"]}

    explanation = await truefoundry_client.generate_reasoning_explanation(res_dict, question)
    return {"explanation": explanation, "resource_id": resource_id}

# ==========================================
# RESOURCES & COST
# ==========================================
@router.get("/resources")
async def list_resources(waste_only: bool = False, refresh: bool = False, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    latest_run = db.query(models.AgentRun).order_by(models.AgentRun.created_at.desc()).first()
    
    # If user requests fresh scan or if no inventory scan exists yet, scan running infrastructure
    if not latest_run or refresh:
        agent = CloudJanitorAgent(db)
        latest_run = await agent.run_discovery_and_planning(
            prompt="Initial cloud inventory discovery upon user login",
            user_id=current_user.username,
            mode="READ_ONLY"
        )
        if not latest_run or latest_run.status == "FAILED":
            return []

    query = db.query(models.ResourceSnapshot).filter(models.ResourceSnapshot.run_id == latest_run.id)
    if waste_only:
        query = query.filter(models.ResourceSnapshot.is_waste == True)
        
    snapshots = query.all()
    return [
        {
            "resource_id": s.resource_id, "resource_type": s.resource_type, "region": s.region,
            "name": s.name, "state": s.state, "instance_type_or_size": s.instance_type_or_size,
            "monthly_cost": s.monthly_cost, "cost_source": s.cost_source, "cost_method": s.cost_method,
            "is_waste": s.is_waste, "confidence": s.confidence, "waste_finding": s.waste_finding,
            "evidence": json.loads(s.evidence_json or "[]"),
            "recommended_action": s.recommended_action, "requires_approval": s.requires_approval
        } for s in snapshots
    ]

@router.post("/resources/scan")
async def scan_live_resources(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Triggers an elastic live scan across all AWS services in the account"""
    agent = CloudJanitorAgent(db)
    run = await agent.run_discovery_and_planning(
        prompt="Live comprehensive AWS infrastructure scan",
        user_id=current_user.username,
        mode="READ_ONLY"
    )
    snapshots = db.query(models.ResourceSnapshot).filter(models.ResourceSnapshot.run_id == run.id).all()
    return {
        "run_id": run.id,
        "status": run.status,
        "total_scanned": run.total_resources_scanned,
        "waste_candidates_count": run.waste_candidates_count,
        "potential_monthly_savings": run.potential_monthly_savings,
        "resources": [
            {
                "resource_id": s.resource_id, "resource_type": s.resource_type, "region": s.region,
                "name": s.name, "state": s.state, "instance_type_or_size": s.instance_type_or_size,
                "monthly_cost": s.monthly_cost, "cost_source": s.cost_source,
                "is_waste": s.is_waste, "confidence": s.confidence, "waste_finding": s.waste_finding,
                "evidence": json.loads(s.evidence_json or "[]"),
                "recommended_action": s.recommended_action, "requires_approval": s.requires_approval
            } for s in snapshots
        ]
    }

@router.post("/resources/{resource_id}/delete")
async def delete_resource_component(
    resource_id: str,
    req: schemas.DirectDeleteRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Direct component deletion endpoint:
    Allows user to select any running AWS component (EC2, S3, RDS, Lambda, EBS, ELB, NAT Gateway, EIP, etc.)
    and securely terminate/delete it inside the sandboxed environment with pre/post live AWS verification.
    """
    if not req.confirmation:
        raise HTTPException(
            status_code=400,
            detail="Deletion blocked: Explicit confirmation checkbox is required to terminate this component."
        )

    session, auth_meta = resolve_aws_session(db)
    if not auth_meta["is_authenticated"]:
        raise HTTPException(status_code=500, detail="Cannot terminate: AWS session could not be authenticated")

    target_region = req.region or auth_meta["region"]

    AuditService.record_event(
        db, action="DIRECT_TERMINATION_REQUESTED", status="PENDING",
        user=current_user.username, aws_account_id=auth_meta["account_id"],
        region=target_region, resource_id=resource_id,
        reason=req.reason or f"User requested direct termination of {req.resource_type} {resource_id}"
    )

    result = ApprovalService.execute_direct_termination(
        db=db,
        session=session,
        resource_id=resource_id,
        resource_type=req.resource_type.lower(),
        region=target_region,
        user_id=current_user.username,
        reason=req.reason
    )

    event_status = "SUCCESS" if result["success"] else "FAILED"
    AuditService.record_event(
        db, action="DIRECT_TERMINATION_COMPLETED" if result["success"] else "DIRECT_TERMINATION_FAILED",
        status=event_status, user=current_user.username, aws_account_id=auth_meta["account_id"],
        region=target_region, resource_id=resource_id,
        reason=result.get("message") or result.get("error"),
        details=result.get("details")
    )

    await ws_manager.broadcast({
        "type": "resource_deleted",
        "resource_id": resource_id,
        "resource_type": req.resource_type,
        "success": result["success"],
        "message": result.get("message") or result.get("error")
    })

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Component termination failed"))

    return result

@router.get("/cost/summary", response_model=schemas.CostSummaryResponse)
def get_cost_summary(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    session, _ = resolve_aws_session(db)
    cost_estimator = CompositeCostEstimator(session)
    billing = cost_estimator.get_account_billing_summary()

    latest_run = db.query(models.AgentRun).order_by(models.AgentRun.created_at.desc()).first()
    potential_monthly = latest_run.potential_monthly_savings if latest_run else 0.0
    candidates_count = latest_run.waste_candidates_count if latest_run else 0

    return schemas.CostSummaryResponse(
        total_monthly_spend=billing["total_monthly_spend"],
        potential_monthly_savings=potential_monthly,
        potential_annual_savings=round(potential_monthly * 12, 2),
        service_breakdown=billing["service_breakdown"],
        candidates_count=candidates_count,
        billing_data_status=billing["status"]
    )

# ==========================================
# CLEANUP PLANS
# ==========================================
@router.get("/plans/latest")
def get_latest_plan(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    plan = db.query(models.CleanupPlan).order_by(models.CleanupPlan.created_at.desc()).first()
    if not plan:
        return None

    snapshots = db.query(models.ResourceSnapshot).filter(
        models.ResourceSnapshot.run_id == plan.run_id,
        models.ResourceSnapshot.is_waste == True
    ).all()

    return {
        "id": plan.id, "run_id": plan.run_id, "aws_account_id": plan.aws_account_id,
        "region": plan.region, "plan_version": plan.plan_version, "plan_hash": plan.plan_hash,
        "status": plan.status, "candidates_count": plan.candidates_count,
        "total_monthly_savings": plan.total_monthly_savings,
        "total_annual_savings": plan.total_annual_savings,
        "risk_summary": plan.risk_summary, "created_at": plan.created_at,
        "candidates": [
            {
                "resource_id": s.resource_id, "resource_type": s.resource_type, "region": s.region,
                "name": s.name, "state": s.state, "monthly_cost": s.monthly_cost,
                "confidence": s.confidence, "waste_finding": s.waste_finding,
                "evidence": json.loads(s.evidence_json or "[]"),
                "recommended_action": s.recommended_action, "requires_approval": s.requires_approval
            } for s in snapshots
        ]
    }

# ==========================================
# APPROVAL GATE & SAFE EXECUTION
# ==========================================
@router.get("/approvals", response_model=List[schemas.ApprovalRequestResponse])
def list_approvals(status_filter: Optional[str] = None, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    query = db.query(models.ApprovalRequest)
    if status_filter:
        query = query.filter(models.ApprovalRequest.status == status_filter)
    reqs = query.order_by(models.ApprovalRequest.created_at.desc()).all()

    return [
        schemas.ApprovalRequestResponse(
            id=r.id, run_id=r.run_id, plan_id=r.plan_id, aws_account_id=r.aws_account_id,
            region=r.region, resource_id=r.resource_id, resource_type=r.resource_type,
            resource_name=r.resource_name, action=r.action, plan_hash=r.plan_hash,
            risk_level=r.risk_level, evidence=json.loads(r.evidence_json or "[]"),
            dependencies=json.loads(r.dependencies_json or "[]"),
            estimated_monthly_cost=r.estimated_monthly_cost,
            estimated_monthly_savings=r.estimated_monthly_savings,
            status=r.status, created_at=r.created_at, expires_at=r.expires_at,
            resolved_at=r.resolved_at, resolved_by=r.resolved_by,
            execution_result=json.loads(r.execution_result_json) if r.execution_result_json else None
        ) for r in reqs
    ]

@router.post("/approvals/{approval_id}/approve")
async def approve_request(approval_id: str, body: schemas.ApprovalDecisionRequest, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    success, msg, req = ApprovalService.resolve_approval(
        db=db, approval_id=approval_id, decision="APPROVED",
        user_id=current_user.username, reason=body.reason or "Explicit user approval via UI"
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    AuditService.record_event(
        db, action="APPROVAL_APPROVED", status="SUCCESS",
        user=current_user.username, resource_id=req.resource_id,
        reason=f"Approved action {req.action} for {req.resource_id}"
    )

    await ws_manager.broadcast({
        "type": "approval_updated", "approval_id": approval_id,
        "status": "APPROVED", "resource_id": req.resource_id
    })

    exec_result = None
    if body.auto_execute:
        session, auth_meta = resolve_aws_session(db)
        if not auth_meta["is_authenticated"]:
            raise HTTPException(status_code=500, detail="Cannot auto-terminate: AWS session could not be authenticated")

        AuditService.record_event(
            db, action="EXECUTION_STARTED", status="PENDING",
            user=current_user.username, aws_account_id=req.aws_account_id,
            region=req.region, resource_id=req.resource_id,
            reason=f"Auto-terminating resource {req.resource_id} immediately upon granted approval"
        )

        exec_result = ApprovalService.validate_and_execute_approved_action(
            db=db, approval_id=approval_id, session=session, current_plan_hash=req.plan_hash
        )

        event_status = "SUCCESS" if exec_result["success"] else "FAILED"
        AuditService.record_event(
            db, action="EXECUTION_COMPLETED" if exec_result["success"] else "EXECUTION_FAILED",
            status=event_status, user=current_user.username, aws_account_id=req.aws_account_id,
            region=req.region, resource_id=req.resource_id,
            reason=exec_result.get("message") or exec_result.get("error"),
            details=exec_result.get("details")
        )

        await ws_manager.broadcast({
            "type": "execution_completed", "approval_id": approval_id,
            "resource_id": req.resource_id, "success": exec_result["success"],
            "status": exec_result["status"], "message": exec_result.get("message") or exec_result.get("error")
        })

    return {
        "success": True,
        "message": msg if not exec_result else f"Approved and auto-terminated: {exec_result.get('message', '')}",
        "approval_id": approval_id,
        "status": "COMPLETED" if (exec_result and exec_result["success"]) else "APPROVED",
        "execution": exec_result
    }

@router.post("/approvals/{approval_id}/reject")
async def reject_request(approval_id: str, body: schemas.ApprovalDecisionRequest, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    success, msg, req = ApprovalService.resolve_approval(
        db=db, approval_id=approval_id, decision="REJECTED",
        user_id=current_user.username, reason=body.reason or "Rejected by user"
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    AuditService.record_event(
        db, action="APPROVAL_REJECTED", status="SUCCESS",
        user=current_user.username, resource_id=req.resource_id,
        reason=f"Rejected action {req.action} for {req.resource_id}"
    )

    await ws_manager.broadcast({
        "type": "approval_updated", "approval_id": approval_id,
        "status": "REJECTED", "resource_id": req.resource_id
    })
    return {"success": True, "message": msg, "approval_id": approval_id, "status": "REJECTED"}

@router.post("/approvals/{approval_id}/execute")
async def execute_approved_cleanup(approval_id: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """
    CRITICAL SAFETY GATE EXECUTION:
    Executes an approved action strictly through sandboxed isolation.
    Enforces that agent mode must be ACTION, approval must be APPROVED, plan hash must match,
    and pre-deletion live checks must pass.
    """
    setting = db.query(models.UserSetting).first()
    if not setting or setting.agent_mode != "ACTION":
        raise HTTPException(
            status_code=403,
            detail="Execution blocked: Agent is in READ_ONLY mode. Enable ACTION mode in Settings before executing destructive actions."
        )

    req = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == approval_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Approval request not found")

    session, auth_meta = resolve_aws_session(db)
    if not auth_meta["is_authenticated"]:
        raise HTTPException(status_code=500, detail="Cannot execute: AWS session could not be authenticated")

    AuditService.record_event(
        db, action="EXECUTION_STARTED", status="PENDING",
        user=current_user.username, aws_account_id=req.aws_account_id,
        region=req.region, resource_id=req.resource_id,
        reason=f"Executing sandboxed cleanup for {req.resource_id}"
    )

    result = ApprovalService.validate_and_execute_approved_action(
        db=db, approval_id=approval_id, session=session, current_plan_hash=req.plan_hash
    )

    event_status = "SUCCESS" if result["success"] else "FAILED"
    AuditService.record_event(
        db, action="EXECUTION_COMPLETED" if result["success"] else "EXECUTION_FAILED",
        status=event_status, user=current_user.username, aws_account_id=req.aws_account_id,
        region=req.region, resource_id=req.resource_id,
        reason=result.get("message") or result.get("error"),
        details=result.get("details")
    )

    await ws_manager.broadcast({
        "type": "execution_completed", "approval_id": approval_id,
        "resource_id": req.resource_id, "success": result["success"],
        "status": result["status"], "message": result.get("message") or result.get("error")
    })

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Execution failed"))

    return result

# ==========================================
# NOTIFICATIONS & AUDIT
# ==========================================
@router.get("/notifications", response_model=List[schemas.NotificationResponse])
def get_notifications(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    notifs = db.query(models.Notification).order_by(models.Notification.created_at.desc()).limit(50).all()
    return [
        schemas.NotificationResponse(
            id=n.id, type=n.type, title=n.title, message=n.message,
            link=n.link, approval_id=n.approval_id, is_read=n.is_read, created_at=n.created_at
        ) for n in notifs
    ]

@router.post("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    n = db.query(models.Notification).filter(models.Notification.id == notif_id).first()
    if n:
        n.is_read = True
        db.commit()
    return {"status": "ok"}

@router.get("/audit", response_model=List[schemas.AuditEventResponse])
def get_audit_trail(run_id: Optional[str] = None, resource_id: Optional[str] = None, action: Optional[str] = None, limit: int = 100, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    events = AuditService.get_events(db, run_id=run_id, resource_id=resource_id, action=action, limit=limit)
    return [
        schemas.AuditEventResponse(
            id=e.id, timestamp=e.timestamp, run_id=e.run_id, user=e.user,
            aws_account_id=e.aws_account_id, region=e.region, resource_id=e.resource_id,
            action=e.action, status=e.status, reason=e.reason, duration_ms=e.duration_ms,
            details=json.loads(e.details_json) if e.details_json else None
        ) for e in events
    ]
