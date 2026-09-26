import datetime
from typing import Dict, Any, List
from botocore.exceptions import ClientError
from ..cost_engine import CompositeCostEstimator

class UnusedLoadBalancerAnalyzer:
    """
    Analyzes Application, Network, and Classic Load Balancers.
    Detects abandoned balancers with zero registered targets, all unhealthy targets, or zero traffic.
    """
    def __init__(self, session, cost_estimator: CompositeCostEstimator):
        self.session = session
        self.cost_estimator = cost_estimator

    def analyze_load_balancers(self) -> List[Dict[str, Any]]:
        candidates = []
        try:
            elbv2 = self.session.client('elbv2')
            resp = elbv2.describe_load_balancers()
        except Exception:
            return []

        for lb in resp.get('LoadBalancers', []):
            arn = lb['LoadBalancerArn']
            name = lb.get('LoadBalancerName', 'Unnamed-LB')
            lb_type = lb.get('Type', 'application')
            state = lb.get('State', {}).get('Code', 'active')
            scheme = lb.get('Scheme', 'internet-facing')
            created_time = lb.get('CreatedTime')
            created_str = created_time.isoformat() if created_time else "Unknown"

            evidence = []
            dependencies = []
            total_targets = 0
            healthy_targets = 0
            target_group_count = 0

            # 1. Inspect Target Groups
            try:
                tg_resp = elbv2.describe_target_groups(LoadBalancerArn=arn)
                target_groups = tg_resp.get('TargetGroups', [])
                target_group_count = len(target_groups)

                for tg in target_groups:
                    tg_arn = tg['TargetGroupArn']
                    tg_name = tg.get('TargetGroupName', 'tg')
                    dependencies.append(f"Target Group: {tg_name}")

                    # Check health
                    th_resp = elbv2.describe_target_health(TargetGroupArn=tg_arn)
                    descriptions = th_resp.get('TargetHealthDescriptions', [])
                    total_targets += len(descriptions)
                    for th in descriptions:
                        h_state = th.get('TargetHealth', {}).get('State', '')
                        if h_state == 'healthy':
                            healthy_targets += 1
            except Exception as e:
                evidence.append(f"Target group inspection notice: {str(e)}")

            # 2. Inspect Listeners
            try:
                lis_resp = elbv2.describe_listeners(LoadBalancerArn=arn)
                listeners = lis_resp.get('Listeners', [])
                for lis in listeners:
                    dependencies.append(f"Listener on port {lis.get('Port')} ({lis.get('Protocol')})")
            except Exception:
                pass

            # Calculate cost
            cost_info = self.cost_estimator.estimate_resource_cost("elb", {
                "type": lb_type
            })

            is_waste = False
            finding = None
            confidence = 0.0
            recommended_action = "retain"

            if target_group_count == 0:
                is_waste = True
                finding = "unused_load_balancer"
                confidence = 0.95
                recommended_action = "delete"
                evidence.append("Load Balancer has NO target groups attached; routing zero traffic")
                evidence.append(f"Incurring ${cost_info['monthly_cost']:.2f}/month baseline AWS management charge")
            elif total_targets == 0:
                is_waste = True
                finding = "unused_load_balancer"
                confidence = 0.90
                recommended_action = "delete"
                evidence.append("Target groups configured, but ZERO backend targets are registered")
                evidence.append("Abandoned infrastructure routing no application traffic")
            elif healthy_targets == 0:
                is_waste = True
                finding = "candidate_for_cleanup"
                confidence = 0.75
                recommended_action = "review"
                evidence.append(f"All {total_targets} registered targets are UNHEALTHY or non-responsive")
                evidence.append("Potential outage or zombie load balancer requiring operator review")

            candidate = {
                "resource_id": arn,
                "resource_type": "elb",
                "region": self.session.region_name or "us-east-1",
                "name": name,
                "state": state,
                "instance_type_or_size": f"{lb_type} ({scheme})",
                "monthly_cost": cost_info["monthly_cost"],
                "cost_source": cost_info["cost_source"],
                "cost_method": cost_info["calculation_method"],
                "is_waste": is_waste,
                "confidence": confidence,
                "waste_finding": finding,
                "evidence": evidence,
                "dependencies": dependencies,
                "recommended_action": recommended_action,
                "requires_approval": is_waste and recommended_action == "delete",
                "tags": {"Type": lb_type, "Scheme": scheme},
                "created_at": created_str
            }
            candidates.append(candidate)

        return candidates
