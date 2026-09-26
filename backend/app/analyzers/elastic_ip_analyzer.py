from typing import Dict, Any, List
from ..cost_engine import CompositeCostEstimator

class UnattachedElasticIPAnalyzer:
    """
    Analyzes Amazon EC2 Elastic IP addresses (EIPs).
    AWS charges $0.005/hour (~$3.65/month) for each unassociated/idle Elastic IP.
    """
    def __init__(self, session, cost_estimator: CompositeCostEstimator):
        self.session = session
        self.cost_estimator = cost_estimator

    def analyze_eips(self) -> List[Dict[str, Any]]:
        candidates = []
        try:
            ec2 = self.session.client('ec2')
            resp = ec2.describe_addresses()
        except Exception:
            return []

        for addr in resp.get('Addresses', []):
            alloc_id = addr.get('AllocationId', addr.get('PublicIp'))
            public_ip = addr.get('PublicIp')
            association_id = addr.get('AssociationId')
            instance_id = addr.get('InstanceId')
            tags = {t['Key']: t['Value'] for t in addr.get('Tags', [])}
            name = tags.get('Name', f"EIP-{public_ip}")

            is_unattached = not association_id and not instance_id
            monthly_cost = 3.65 # AWS standard: $0.005/hr * 730 hours

            evidence = []
            is_waste = False
            finding = None
            recommended_action = "retain"
            confidence = 0.0

            if is_unattached:
                is_waste = True
                finding = "unattached_elastic_ip"
                confidence = 0.98
                recommended_action = "release"
                evidence.append(f"Elastic IP {public_ip} is allocated but NOT associated with any EC2 instance or network interface")
                evidence.append("AWS imposes continuous penalty charges ($0.005/hr) on unassociated public IPv4 addresses")
            else:
                evidence.append(f"Associated with instance/interface: {instance_id or association_id}")

            candidates.append({
                "resource_id": alloc_id,
                "resource_type": "eip",
                "region": self.session.region_name or "us-east-1",
                "name": name,
                "state": "unassociated" if is_unattached else "associated",
                "instance_type_or_size": f"IPv4: {public_ip}",
                "monthly_cost": monthly_cost if is_unattached else 0.0,
                "cost_source": "aws_pricing_derived",
                "cost_method": "AWS IPv4 idle allocation fee: $0.005/hr × 730 hrs",
                "is_waste": is_waste,
                "confidence": confidence,
                "waste_finding": finding,
                "evidence": evidence,
                "dependencies": [] if is_unattached else [f"Associated to {instance_id}"],
                "recommended_action": recommended_action,
                "requires_approval": is_waste and recommended_action == "release",
                "tags": tags,
                "created_at": None
            })

        return candidates
