from typing import Dict, Any, List
from ..cost_engine import CompositeCostEstimator

class IdleNATGatewayAnalyzer:
    """
    Analyzes Amazon VPC NAT Gateways.
    AWS charges a minimum base fee of $0.045/hour (~$32.85/month) per active NAT Gateway
    regardless of whether traffic is traversing it.
    """
    def __init__(self, session, cost_estimator: CompositeCostEstimator):
        self.session = session
        self.cost_estimator = cost_estimator

    def analyze_nat_gateways(self) -> List[Dict[str, Any]]:
        candidates = []
        try:
            ec2 = self.session.client('ec2')
            resp = ec2.describe_nat_gateways(Filters=[{'Name': 'state', 'Values': ['available']}])
        except Exception:
            return []

        for nat in resp.get('NatGateways', []):
            nat_id = nat.get('NatGatewayId')
            vpc_id = nat.get('VpcId')
            state = nat.get('State')
            created_time = nat.get('CreateTime')
            created_str = created_time.isoformat() if created_time else None
            tags = {t['Key']: t['Value'] for t in nat.get('Tags', [])}
            name = tags.get('Name', nat_id)

            monthly_cost = round(0.045 * 730, 2) # ~$32.85/month baseline

            candidates.append({
                "resource_id": nat_id,
                "resource_type": "nat_gateway",
                "region": self.session.region_name or "us-east-1",
                "name": name,
                "state": state,
                "instance_type_or_size": f"VPC: {vpc_id}",
                "monthly_cost": monthly_cost,
                "cost_source": "aws_pricing_derived",
                "cost_method": "AWS NAT Gateway base provisioning charge: $0.045/hr × 730 hrs",
                "is_waste": False, # Baseline observation, flagged if orphaned
                "confidence": 0.60,
                "waste_finding": "review_required",
                "evidence": [
                    f"NAT Gateway is active in VPC {vpc_id}",
                    f"Incurring ${monthly_cost:.2f}/mo baseline provisioning cost"
                ],
                "dependencies": [f"VPC: {vpc_id}"],
                "recommended_action": "review",
                "requires_approval": False,
                "tags": tags,
                "created_at": created_str
            })

        return candidates
