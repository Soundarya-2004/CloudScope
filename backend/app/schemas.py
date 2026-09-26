from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class AWSIdentityResponse(BaseModel):
    account_id: str
    arn: str
    user_id: str
    region: str
    auth_mode: str = "environment"
    agent_mode: str = "READ_ONLY" # READ_ONLY or ACTION
    is_authenticated: bool = True
    read_permissions_valid: bool = True
    destructive_permissions_valid: bool = False
    warning: Optional[str] = None

class AWSConnectRequest(BaseModel):
    aws_access_key: Optional[str] = None
    aws_secret_key: Optional[str] = None
    aws_region: str = "us-east-1"
    auth_mode: str = "auto" # auto, env, profile, explicit

class ResourceCandidate(BaseModel):
    resource_id: str
    resource_type: str # ec2, ebs, elb, rds, s3, lambda
    region: str
    name: str = "Unnamed"
    state: str
    instance_type_or_size: Optional[str] = None
    monthly_cost: float = 0.0
    cost_source: str = "calculated_estimate" # aws_cost_explorer, aws_pricing_derived, calculated_estimate, unavailable
    cost_method: Optional[str] = None
    is_waste: bool = False
    confidence: float = 0.0
    waste_finding: Optional[str] = None # potentially_idle, likely_orphaned, unused_load_balancer, review_required
    evidence: List[str] = []
    dependencies: List[str] = []
    recommended_action: str = "retain" # terminate, delete, retain, review
    requires_approval: bool = False
    tags: Dict[str, str] = {}
    created_at: Optional[str] = None

class CostItem(BaseModel):
    resource_id: str
    resource_type: str
    monthly_cost: float
    potential_monthly_savings: float
    potential_annual_savings: float
    currency: str = "USD"
    cost_source: str # aws_cost_explorer, aws_pricing_derived, calculated_estimate, unavailable
    confidence: str = "high" # high, medium, low, estimated
    calculation_method: str

class CostSummaryResponse(BaseModel):
    total_monthly_spend: float = 0.0
    potential_monthly_savings: float = 0.0
    potential_annual_savings: float = 0.0
    currency: str = "USD"
    cost_sources: Dict[str, int] = {}
    service_breakdown: Dict[str, float] = {}
    candidates_count: int = 0
    billing_data_status: str = "available" # available, permission_denied, estimated_only

class CleanupPlanResponse(BaseModel):
    id: str
    run_id: str
    aws_account_id: str
    region: str
    plan_version: int = 1
    plan_hash: str
    status: str
    candidates_count: int
    total_monthly_savings: float
    total_annual_savings: float
    risk_summary: Optional[str] = None
    candidates: List[ResourceCandidate] = []
    created_at: datetime

class ApprovalRequestResponse(BaseModel):
    id: str
    run_id: str
    plan_id: str
    aws_account_id: str
    region: str
    resource_id: str
    resource_type: str
    resource_name: str
    action: str
    plan_hash: str
    risk_level: str
    evidence: List[str] = []
    dependencies: List[str] = []
    estimated_monthly_cost: float
    estimated_monthly_savings: float
    status: str
    created_at: datetime
    expires_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None

class ApprovalDecisionRequest(BaseModel):
    reason: Optional[str] = "Approved via UI"
    auto_execute: bool = False

class DirectDeleteRequest(BaseModel):
    resource_type: str
    region: Optional[str] = None
    reason: Optional[str] = "Direct component termination requested by user"
    confirmation: bool = False

class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    message: str
    link: Optional[str] = None
    approval_id: Optional[str] = None
    is_read: bool = False
    created_at: datetime

class AuditEventResponse(BaseModel):
    id: str
    timestamp: datetime
    run_id: Optional[str] = None
    user: str
    aws_account_id: Optional[str] = None
    region: Optional[str] = None
    resource_id: Optional[str] = None
    action: str
    status: str
    reason: Optional[str] = None
    duration_ms: int = 0
    details: Optional[Dict[str, Any]] = None

class AgentRunRequest(BaseModel):
    prompt: str = "Find the AWS resources that are costing me money but appear unused."
    mode: Optional[str] = None # READ_ONLY or ACTION
    region: Optional[str] = None

class AgentRunResponse(BaseModel):
    id: str
    prompt: str
    status: str
    mode: str
    aws_account_id: Optional[str] = None
    region: Optional[str] = None
    total_resources_scanned: int = 0
    waste_candidates_count: int = 0
    potential_monthly_savings: float = 0.0
    summary: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

class AgentModeToggleRequest(BaseModel):
    mode: str = Field(..., pattern="^(READ_ONLY|ACTION)$")
    confirmation: bool = False

class UserResponse(BaseModel):
    username: str
    role: str
