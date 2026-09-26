import datetime
from typing import Dict, Any, List, Optional, Tuple
from botocore.exceptions import ClientError
from ..cost_engine import CompositeCostEstimator

class IdleEC2Analyzer:
    """
    Analyzes Amazon EC2 instances to identify potentially idle or abandoned compute resources.
    Combines instance state, CloudWatch CPU metrics, attached EBS dependencies, tags, and lifecycle age.
    """
    def __init__(self, session, cost_estimator: CompositeCostEstimator):
        self.session = session
        self.cost_estimator = cost_estimator

    def get_cpu_metrics(self, instance_id: str, days: int = 7) -> Tuple[Optional[float], Optional[float], str]:
        """Queries CloudWatch for average and peak CPU utilization over the observation window"""
        try:
            cw = self.session.client('cloudwatch')
            end_time = datetime.datetime.utcnow()
            start_time = end_time - datetime.timedelta(days=days)
            
            resp = cw.get_metric_statistics(
                Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=start_time,
                EndTime=end_time,
                Period=86400, # Daily data points
                Statistics=['Average', 'Maximum']
            )
            datapoints = resp.get('Datapoints', [])
            if not datapoints:
                return None, None, f"No CloudWatch CPU metrics recorded in the last {days} days"
                
            avg_cpu = sum(dp['Average'] for dp in datapoints) / len(datapoints)
            max_cpu = max(dp['Maximum'] for dp in datapoints)
            return round(avg_cpu, 2), round(max_cpu, 2), f"CloudWatch metrics analyzed across {len(datapoints)} daily checkpoints"
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Error")
            return None, None, f"CloudWatch metric query unavailable ({code})"
        except Exception as e:
            return None, None, f"CloudWatch metric check omitted: {str(e)}"

    def analyze_instances(self) -> List[Dict[str, Any]]:
        candidates = []
        try:
            ec2 = self.session.client('ec2')
            resp = ec2.describe_instances()
        except Exception as e:
            # Re-raise or log - never fake data!
            return []

        for reservation in resp.get('Reservations', []):
            for inst in reservation.get('Instances', []):
                instance_id = inst['InstanceId']
                state = inst.get('State', {}).get('Name', 'unknown')
                instance_type = inst.get('InstanceType', 'unknown')
                launch_time = inst.get('LaunchTime')
                launch_str = launch_time.isoformat() if launch_time else "Unknown"
                
                # Tags
                tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
                name = tags.get('Name', instance_id)
                
                # Dependencies (attached EBS volumes, Network interfaces)
                dependencies = []
                for bdm in inst.get('BlockDeviceMappings', []):
                    ebs = bdm.get('Ebs', {})
                    vol_id = ebs.get('VolumeId')
                    dev_name = bdm.get('DeviceName')
                    if vol_id:
                        dependencies.append(f"Attached EBS volume {vol_id} on {dev_name}")
                
                # Calculate cost
                cost_info = self.cost_estimator.estimate_resource_cost("ec2", {
                    "instance_type": instance_type,
                    "state": state
                })

                # Check production safeguards
                is_prod = any(
                    k.lower() in ['env', 'environment', 'stage'] and any(p in v.lower() for p in ['prod', 'production', 'live'])
                    for k, v in tags.items()
                ) or any('prod' in v.lower() for v in tags.values())

                evidence = []
                is_candidate = False
                finding = None
                confidence = 0.0
                recommended_action = "retain"

                # Check 1: Running with low CPU utilization
                if state == "running":
                    avg_cpu, max_cpu, cw_msg = self.get_cpu_metrics(instance_id)
                    evidence.append(cw_msg)

                    if avg_cpu is not None and max_cpu is not None:
                        evidence.append(f"Average CPU utilization: {avg_cpu}%, Peak CPU: {max_cpu}% over observation window")
                        if avg_cpu < 5.0 and max_cpu < 15.0:
                            is_candidate = True
                            finding = "potentially_idle"
                            confidence = 0.88 if avg_cpu < 2.0 else 0.75
                            evidence.append("Consistent near-zero compute utilization indicates potential abandoned workload")
                            recommended_action = "terminate"
                    else:
                        # CloudWatch unavailable or no datapoints
                        # If recently launched, not enough history
                        pass

                # Check 2: Stopped instances
                elif state == "stopped":
                    is_candidate = True
                    finding = "candidate_for_cleanup"
                    confidence = 0.80
                    evidence.append("Instance is in stopped state; compute is inactive but attached storage costs continue")
                    recommended_action = "terminate"

                # If production safeguard triggered, downgrade action to review
                if is_candidate and is_prod:
                    finding = "review_required"
                    recommended_action = "review"
                    confidence = 0.40
                    evidence.append("PROTECTION WARNING: Instance tags indicate production/critical environment. Requires manual review.")

                candidate = {
                    "resource_id": instance_id,
                    "resource_type": "ec2",
                    "region": self.session.region_name or "us-east-1",
                    "name": name,
                    "state": state,
                    "instance_type_or_size": instance_type,
                    "monthly_cost": cost_info["monthly_cost"],
                    "cost_source": cost_info["cost_source"],
                    "cost_method": cost_info["calculation_method"],
                    "is_waste": is_candidate,
                    "confidence": confidence,
                    "waste_finding": finding,
                    "evidence": evidence,
                    "dependencies": dependencies,
                    "recommended_action": recommended_action,
                    "requires_approval": is_candidate and recommended_action == "terminate",
                    "tags": tags,
                    "created_at": launch_str
                }
                candidates.append(candidate)

        return candidates
