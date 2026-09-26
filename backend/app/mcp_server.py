"""
Model Context Protocol (MCP) Server for CloudScope AWS Tools.
Exposes AWS discovery, cost estimation, planning, and sandboxed execution tools to TrueForge.
"""
import sys
import json
import asyncio
from typing import Dict, Any, List
from .database import SessionLocal
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
from . import models

TOOLS = [
    {
        "name": "aws_discover_infrastructure",
        "description": "Scans real AWS infrastructure (EC2, EBS, ELB) and identifies potentially idle or orphaned resources with evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "region": {"type": "string", "description": "AWS Region, e.g. us-east-1"}
            }
        }
    },
    {
        "name": "aws_estimate_costs",
        "description": "Calculates real monthly and annual cost estimates for discovered infrastructure using AWS pricing rates.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_type": {"type": "string", "enum": ["ec2", "ebs", "elb"]},
                "resource_data": {"type": "object"}
            },
            "required": ["resource_type", "resource_data"]
        }
    },
    {
        "name": "aws_generate_cleanup_plan",
        "description": "Generates a cryptographic plan hash and structured teardown plan. Halts before any destructive action.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "User intent or query"}
            }
        }
    },
    {
        "name": "aws_execute_approved_action",
        "description": "Executes a destructive cleanup action inside the secure sandbox ONLY if explicit human approval is valid and verified.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "approval_id": {"type": "string", "description": "Unique ID of the approved action"}
            },
            "required": ["approval_id"]
        }
    }
]

def handle_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        session, auth = resolve_aws_session(db)
        if not auth["is_authenticated"]:
            return {"error": f"AWS connection failed: {auth['error']}"}

        cost_estimator = CompositeCostEstimator(session)

        if tool_name == "aws_discover_infrastructure":
            all_res = []
            all_res.extend(IdleEC2Analyzer(session, cost_estimator).analyze_instances())
            all_res.extend(OrphanedEBSAnalyzer(session, cost_estimator).analyze_volumes())
            all_res.extend(UnusedLoadBalancerAnalyzer(session, cost_estimator).analyze_load_balancers())
            all_res.extend(UnattachedElasticIPAnalyzer(session, cost_estimator).analyze_eips())
            all_res.extend(IdleNATGatewayAnalyzer(session, cost_estimator).analyze_nat_gateways())
            all_res.extend(RDSAnalyzer(session, cost_estimator).analyze_databases())
            all_res.extend(S3BucketAnalyzer(session, cost_estimator).analyze_buckets())
            all_res.extend(LambdaAnalyzer(session, cost_estimator).analyze_functions())
            
            # Global Elastic Scanner
            known_ids = {c["resource_id"] for c in all_res}
            all_res.extend(GlobalResourceScanner(session, cost_estimator).scan_all_services(known_ids))

            return {
                "account_id": auth["account_id"],
                "region": auth["region"],
                "total_scanned": len(all_res),
                "waste_candidates": [c for c in all_res if c["is_waste"]],
                "all_resources": all_res
            }

        elif tool_name == "aws_estimate_costs":
            res_type = arguments.get("resource_type")
            res_data = arguments.get("resource_data", {})
            return cost_estimator.estimate_resource_cost(res_type, res_data)

        elif tool_name == "aws_execute_approved_action":
            app_id = arguments.get("approval_id")
            req = db.query(models.ApprovalRequest).filter(models.ApprovalRequest.id == app_id).first()
            if not req:
                return {"error": "Approval request not found"}
            res = ApprovalService.validate_and_execute_approved_action(db, app_id, session, req.plan_hash)
            return res

        return {"error": f"Unknown tool '{tool_name}'"}
    finally:
        db.close()

def main():
    """Stdio JSON-RPC MCP loop for TrueForge integration"""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            method = req.get("method")
            msg_id = req.get("id")

            if method == "tools/list":
                response = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
            elif method == "tools/call":
                params = req.get("params", {})
                name = params.get("name")
                args = params.get("arguments", {})
                res = handle_tool_call(name, args)
                response = {"jsonrpc": "2.0", "id": msg_id, "result": {"content": [{"type": "text", "text": json.dumps(res, indent=2)}]}}
            else:
                response = {"jsonrpc": "2.0", "id": msg_id, "result": {}}

            print(json.dumps(response), flush=True)
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}
            print(json.dumps(err_resp), flush=True)

if __name__ == "__main__":
    main()
