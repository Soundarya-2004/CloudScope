import datetime
from typing import Dict, Any, List
from ..cost_engine import CompositeCostEstimator

class OrphanedEBSAnalyzer:
    """
    Analyzes Amazon Elastic Block Store (EBS) volumes to identify unattached, orphaned storage.
    Unattached volumes in 'available' state continue to incur 100% hourly storage charges without serving any instances.
    """
    def __init__(self, session, cost_estimator: CompositeCostEstimator):
        self.session = session
        self.cost_estimator = cost_estimator

    def analyze_volumes(self) -> List[Dict[str, Any]]:
        candidates = []
        try:
            ec2 = self.session.client('ec2')
            resp = ec2.describe_volumes()
        except Exception:
            return []

        now = datetime.datetime.utcnow()

        for vol in resp.get('Volumes', []):
            vol_id = vol['VolumeId']
            state = vol.get('State', 'unknown')
            size_gb = vol.get('Size', 0)
            vol_type = vol.get('VolumeType', 'gp3')
            create_time = vol.get('CreateTime')
            create_str = create_time.isoformat() if create_time else "Unknown"
            snapshot_id = vol.get('SnapshotId', '')
            
            # Tags
            tags = {t['Key']: t['Value'] for t in vol.get('Tags', [])}
            name = tags.get('Name', vol_id)

            # Check attachments
            attachments = vol.get('Attachments', [])
            is_unattached = (state == 'available' or len(attachments) == 0)

            # Calculate cost
            cost_info = self.cost_estimator.estimate_resource_cost("ebs", {
                "size": size_gb,
                "volume_type": vol_type
            })

            evidence = []
            dependencies = []
            is_waste = False
            finding = None
            confidence = 0.0
            recommended_action = "retain"

            if is_unattached:
                is_waste = True
                finding = "likely_orphaned"
                confidence = 0.92
                recommended_action = "delete"
                
                evidence.append(f"Volume is in '{state}' state and unattached from all compute instances")
                evidence.append(f"Capacity: {size_gb} GiB ({vol_type}) incurring continuous passive storage fees")

                if create_time:
                    age_days = (now - create_time.replace(tzinfo=None)).days
                    evidence.append(f"Volume has existed for {age_days} days (Created: {create_time.strftime('%Y-%m-%d')})")

                if snapshot_id:
                    evidence.append(f"Created from snapshot: {snapshot_id}")
                    dependencies.append(f"Source snapshot: {snapshot_id}")
                else:
                    evidence.append("No source snapshot recorded; volume deletion will permanently destroy unbacked-up data")
                    dependencies.append("CAUTION: No parent snapshot detected")

                # Production tag check
                is_prod = any(
                    k.lower() in ['env', 'environment', 'stage'] and any(p in v.lower() for p in ['prod', 'production', 'live'])
                    for k, v in tags.items()
                ) or any('prod' in v.lower() for v in tags.values())

                if is_prod:
                    finding = "review_required"
                    recommended_action = "review"
                    confidence = 0.45
                    evidence.append("PROTECTION WARNING: Tags indicate production or critical data. Manual verification required.")
            else:
                for att in attachments:
                    dependencies.append(f"Attached to instance {att.get('InstanceId')} as {att.get('Device')}")

            candidate = {
                "resource_id": vol_id,
                "resource_type": "ebs",
                "region": self.session.region_name or "us-east-1",
                "name": name,
                "state": state,
                "instance_type_or_size": f"{size_gb} GiB {vol_type}",
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
                "tags": tags,
                "created_at": create_str
            }
            candidates.append(candidate)

        return candidates
