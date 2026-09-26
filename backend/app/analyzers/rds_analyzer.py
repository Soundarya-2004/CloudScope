from typing import Dict, Any, List
from ..cost_engine import CompositeCostEstimator

class RDSAnalyzer:
    """
    Analyzes Amazon Relational Database Service (RDS) instances.
    Identifies stopped DB instances (which still bill for 100% of provisioned storage),
    and non-production instances left running.
    """
    def __init__(self, session, cost_estimator: CompositeCostEstimator):
        self.session = session
        self.cost_estimator = cost_estimator

    def analyze_databases(self) -> List[Dict[str, Any]]:
        candidates = []
        try:
            rds = self.session.client('rds')
            resp = rds.describe_db_instances()
        except Exception:
            return []

        for db in resp.get('DBInstances', []):
            db_id = db.get('DBInstanceIdentifier')
            engine = db.get('Engine')
            instance_class = db.get('DBInstanceClass')
            status = db.get('DBInstanceStatus')
            storage_gb = db.get('AllocatedStorage', 20)
            multi_az = db.get('MultiAZ', False)

            tags_resp = db.get('TagList', [])
            tags = {t['Key']: t['Value'] for t in tags_resp}

            is_prod = any(
                k.lower() in ['env', 'environment', 'stage'] and any(p in v.lower() for p in ['prod', 'production', 'live'])
                for k, v in tags.items()
            ) or 'prod' in db_id.lower()

            # Estimate cost: standard db.t3.medium benchmark ~$0.068/hr + $0.115/GB storage
            storage_cost = storage_gb * 0.115
            compute_cost = 0.068 * 730 if status == 'available' else 0.0
            monthly_cost = round(compute_cost + storage_cost, 2)

            evidence = []
            is_waste = False
            finding = None
            recommended_action = "retain"
            confidence = 0.0

            if status == 'stopped':
                is_waste = True
                finding = "candidate_for_cleanup"
                confidence = 0.70
                recommended_action = "review"
                evidence.append(f"RDS database is in stopped state; still billed ${storage_cost:.2f}/mo for {storage_gb} GiB storage")
                evidence.append("AWS auto-restarts stopped RDS instances after 7 days, potentially re-incurring compute charges")
            elif not is_prod and ('dev' in db_id.lower() or 'test' in db_id.lower()):
                is_waste = True
                finding = "potentially_idle"
                confidence = 0.65
                recommended_action = "review"
                evidence.append(f"Identified as non-production database ({db_id}) running 24/7 ({instance_class})")
                evidence.append("Candidate for scheduled shutdown outside working hours")

            if is_prod and is_waste:
                finding = "review_required"
                recommended_action = "review"
                confidence = 0.30
                evidence.append("CRITICAL: Database flagged as Production. Automated cleanup strictly blocked.")

            candidates.append({
                "resource_id": db_id,
                "resource_type": "rds",
                "region": self.session.region_name or "us-east-1",
                "name": db_id,
                "state": status,
                "instance_type_or_size": f"{engine} ({instance_class}, {storage_gb}GB)",
                "monthly_cost": monthly_cost,
                "cost_source": "aws_pricing_derived",
                "cost_method": f"RDS {instance_class} compute (${compute_cost:.2f}) + {storage_gb}GB storage (${storage_cost:.2f})",
                "is_waste": is_waste,
                "confidence": confidence,
                "waste_finding": finding,
                "evidence": evidence,
                "dependencies": [f"Engine: {engine}", f"Multi-AZ: {multi_az}"],
                "recommended_action": recommended_action,
                "requires_approval": is_waste and recommended_action in ["stop", "delete"],
                "tags": tags,
                "created_at": None
            })

        return candidates
