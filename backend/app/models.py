import datetime
import uuid
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String, nullable=True)
    role = Column(String, default="Admin") # Admin or View-only

class UserSetting(Base):
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    aws_access_key = Column(String, nullable=True, index=True)
    aws_secret_key = Column(String, nullable=True)  # Fernet encrypted
    aws_region = Column(String, default="us-east-1")
    aws_account_id = Column(String, nullable=True)
    aws_arn = Column(String, nullable=True)
    auth_mode = Column(String, default="auto") # auto, env, profile, explicit
    agent_mode = Column(String, default="READ_ONLY") # READ_ONLY or ACTION
    is_configured = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class AgentRun(Base):
    __tablename__ = "agent_runs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    prompt = Column(String, nullable=False)
    status = Column(String, default="PENDING") # PENDING, DISCOVERING, ANALYZING, PLANNING, WAITING_APPROVAL, EXECUTING, COMPLETED, FAILED
    mode = Column(String, default="READ_ONLY") # READ_ONLY or ACTION
    aws_account_id = Column(String, nullable=True)
    region = Column(String, nullable=True)
    total_resources_scanned = Column(Integer, default=0)
    waste_candidates_count = Column(Integer, default=0)
    potential_monthly_savings = Column(Float, default=0.0)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class ResourceSnapshot(Base):
    __tablename__ = "resource_snapshots"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("agent_runs.id"), index=True)
    resource_id = Column(String, index=True, nullable=False)
    resource_type = Column(String, index=True, nullable=False) # ec2, ebs, elb, rds, s3, lambda
    region = Column(String, nullable=False)
    name = Column(String, default="Unnamed")
    state = Column(String, nullable=False)
    instance_type_or_size = Column(String, nullable=True)
    monthly_cost = Column(Float, default=0.0)
    cost_source = Column(String, default="calculated_estimate") # aws_cost_explorer, aws_pricing_derived, calculated_estimate, unavailable
    is_waste = Column(Boolean, default=False)
    confidence = Column(Float, default=0.0)
    waste_finding = Column(String, nullable=True) # potentially_idle, likely_orphaned, unused_load_balancer, review_required
    evidence_json = Column(Text, nullable=True)
    recommended_action = Column(String, default="retain") # terminate, delete, retain, review
    requires_approval = Column(Boolean, default=False)
    scanned_at = Column(DateTime, default=datetime.datetime.utcnow)

class CleanupPlan(Base):
    __tablename__ = "cleanup_plans"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("agent_runs.id"), index=True)
    aws_account_id = Column(String, nullable=True)
    region = Column(String, nullable=True)
    plan_version = Column(Integer, default=1)
    plan_hash = Column(String, nullable=False, index=True)
    status = Column(String, default="DRAFT") # DRAFT, PENDING_APPROVAL, PARTIALLY_APPROVED, EXECUTED, CANCELLED
    candidates_count = Column(Integer, default=0)
    total_monthly_savings = Column(Float, default=0.0)
    total_annual_savings = Column(Float, default=0.0)
    risk_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    run_id = Column(String, ForeignKey("agent_runs.id"), index=True)
    plan_id = Column(String, ForeignKey("cleanup_plans.id"), index=True)
    user_id = Column(String, default="admin")
    aws_account_id = Column(String, nullable=False)
    region = Column(String, nullable=False)
    resource_id = Column(String, index=True, nullable=False)
    resource_type = Column(String, nullable=False)
    resource_name = Column(String, default="Unnamed")
    action = Column(String, nullable=False) # terminate_ec2, delete_ebs, delete_elb
    plan_hash = Column(String, nullable=False)
    risk_level = Column(String, default="HIGH") # LOW, MEDIUM, HIGH, CRITICAL
    evidence_json = Column(Text, nullable=True)
    dependencies_json = Column(Text, nullable=True)
    estimated_monthly_cost = Column(Float, default=0.0)
    estimated_monthly_savings = Column(Float, default=0.0)
    status = Column(String, default="PENDING") # PENDING, APPROVED, REJECTED, EXPIRED, EXECUTING, COMPLETED, FAILED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)
    execution_result_json = Column(Text, nullable=True)

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    type = Column(String, default="info") # approval_required, execution_success, execution_failure, warning, info
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    link = Column(String, nullable=True)
    approval_id = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    run_id = Column(String, nullable=True, index=True)
    user = Column(String, default="system")
    aws_account_id = Column(String, nullable=True)
    region = Column(String, nullable=True)
    resource_id = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True) # AGENT_STARTED, AWS_CONNECTED, DISCOVERY_STARTED, etc.
    status = Column(String, nullable=False) # SUCCESS, FAILED, BLOCKED, PENDING
    reason = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0)
    details_json = Column(Text, nullable=True)
