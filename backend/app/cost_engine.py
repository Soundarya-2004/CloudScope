import datetime
from typing import Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod

# Standard AWS on-demand hourly pricing benchmarks (US East / standard regions, USD)
# Used for transparent, verified AWS pricing-derived estimates when Cost Explorer is not enabled or cannot attribute at the resource level
EC2_HOURLY_RATES: Dict[str, float] = {
    # Micro & Nano
    "t2.nano": 0.0058, "t2.micro": 0.0116, "t2.small": 0.023, "t2.medium": 0.0464, "t2.large": 0.0928, "t2.xlarge": 0.1856,
    "t3.nano": 0.0052, "t3.micro": 0.0104, "t3.small": 0.0208, "t3.medium": 0.0416, "t3.large": 0.0832, "t3.xlarge": 0.1664, "t3.2xlarge": 0.3328,
    "t4g.nano": 0.0042, "t4g.micro": 0.0084, "t4g.small": 0.0168, "t4g.medium": 0.0336, "t4g.large": 0.0672, "t4g.xlarge": 0.1344,
    # General Purpose
    "m5.large": 0.096, "m5.xlarge": 0.192, "m5.2xlarge": 0.384, "m5.4xlarge": 0.768,
    "m6i.large": 0.096, "m6i.xlarge": 0.192, "m6i.2xlarge": 0.384,
    # Compute Optimized
    "c5.large": 0.085, "c5.xlarge": 0.17, "c5.2xlarge": 0.34, "c5.4xlarge": 0.68,
    "c6i.large": 0.085, "c6i.xlarge": 0.17,
    # Memory Optimized
    "r5.large": 0.126, "r5.xlarge": 0.252, "r5.2xlarge": 0.504
}

# Standard AWS EBS storage pricing per GiB-month (USD)
EBS_PER_GB_MONTHLY_RATES: Dict[str, float] = {
    "gp3": 0.08,        # General Purpose SSD (gp3)
    "gp2": 0.10,        # General Purpose SSD (gp2)
    "io1": 0.125,       # Provisioned IOPS SSD
    "io2": 0.125,       # Provisioned IOPS SSD (io2)
    "st1": 0.045,       # Throughput Optimized HDD
    "sc1": 0.015,       # Cold HDD
    "standard": 0.05    # Magnetic
}

# Standard ALB/NLB baseline pricing (USD): ~$0.0225/hour baseline = ~$16.43/month
ELB_HOURLY_BASELINE: float = 0.0225

HOURS_PER_MONTH: float = 730.0

class BaseCostEstimator(ABC):
    @abstractmethod
    def estimate_cost(self, resource_type: str, resource_data: Dict[str, Any]) -> Dict[str, Any]:
        """Returns structured cost estimate"""
        pass

class ResourcePricingEstimator(BaseCostEstimator):
    """
    Calculates transparent cost estimates based on published AWS on-demand pricing rates.
    Always includes the exact calculation formula and method.
    """
    def estimate_cost(self, resource_type: str, resource_data: Dict[str, Any]) -> Dict[str, Any]:
        if resource_type == "ec2":
            instance_type = resource_data.get("instance_type", "t3.micro")
            state = resource_data.get("state", "running")
            hourly_rate = EC2_HOURLY_RATES.get(instance_type, 0.0416) # Default to t3.medium benchmark if custom
            
            if state == "running":
                monthly = round(hourly_rate * HOURS_PER_MONTH, 2)
                method = f"AWS on-demand rate ${hourly_rate:.4f}/hr × 730 hrs/month for {instance_type}"
            else:
                # Stopped instances incur $0 compute, but attached EBS costs continue
                monthly = 0.0
                method = f"Stopped EC2 instance (compute cost $0.00/hr, attached storage billed separately)"
                
            return {
                "monthly_cost": monthly,
                "currency": "USD",
                "cost_source": "aws_pricing_derived",
                "period": "monthly",
                "confidence": "high" if instance_type in EC2_HOURLY_RATES else "medium",
                "calculation_method": method
            }

        elif resource_type == "ebs":
            size_gb = float(resource_data.get("size", 20))
            vol_type = resource_data.get("volume_type", "gp3")
            rate_per_gb = EBS_PER_GB_MONTHLY_RATES.get(vol_type, 0.08)
            monthly = round(size_gb * rate_per_gb, 2)
            
            return {
                "monthly_cost": monthly,
                "currency": "USD",
                "cost_source": "aws_pricing_derived",
                "period": "monthly",
                "confidence": "high",
                "calculation_method": f"AWS EBS {vol_type} rate ${rate_per_gb:.3f}/GiB-month × {size_gb} GiB"
            }

        elif resource_type == "elb":
            monthly = round(ELB_HOURLY_BASELINE * HOURS_PER_MONTH, 2)
            return {
                "monthly_cost": monthly,
                "currency": "USD",
                "cost_source": "aws_pricing_derived",
                "period": "monthly",
                "confidence": "high",
                "calculation_method": f"AWS Elastic Load Balancing baseline charge ${ELB_HOURLY_BASELINE:.4f}/hr × 730 hrs/month"
            }

        return {
            "monthly_cost": 0.0,
            "currency": "USD",
            "cost_source": "unavailable",
            "period": "monthly",
            "confidence": "low",
            "calculation_method": "Cost estimation not available for this resource type"
        }

class CostExplorerEstimator(BaseCostEstimator):
    """
    Attempts to pull actual billing metrics from AWS Cost Explorer API.
    """
    def __init__(self, session):
        self.session = session
        self._cached_service_costs = None

    def get_service_costs(self) -> Dict[str, float]:
        if self._cached_service_costs is not None:
            return self._cached_service_costs
            
        try:
            ce = self.session.client('ce')
            today = datetime.date.today()
            start = today.replace(day=1).strftime('%Y-%m-%d')
            end = (today + datetime.timedelta(days=1)).strftime('%Y-%m-%d')
            
            resp = ce.get_cost_and_usage(
                TimePeriod={'Start': start, 'End': end},
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
            )
            
            services = {}
            if resp.get('ResultsByTime'):
                for group in resp['ResultsByTime'][0].get('Groups', []):
                    svc = group['Keys'][0]
                    amt = float(group['Metrics']['UnblendedCost']['Amount'])
                    services[svc] = round(amt, 2)
            self._cached_service_costs = services
            return services
        except Exception:
            self._cached_service_costs = {}
            return {}

    def estimate_cost(self, resource_type: str, resource_data: Dict[str, Any]) -> Dict[str, Any]:
        # Cost Explorer cannot attribute per-resource costs directly without AWS Cost Allocation Tags
        # Return fallback indication
        return {
            "monthly_cost": 0.0,
            "currency": "USD",
            "cost_source": "unavailable",
            "period": "monthly",
            "confidence": "low",
            "calculation_method": "Direct resource attribution requires AWS Cost Allocation Tags"
        }

class CompositeCostEstimator:
    """
    Composite estimator that queries Cost Explorer for high-level billing context
    and combines with ResourcePricingEstimator for accurate resource-level calculations.
    """
    def __init__(self, session=None):
        self.pricing_estimator = ResourcePricingEstimator()
        self.ce_estimator = CostExplorerEstimator(session) if session else None

    def estimate_resource_cost(self, resource_type: str, resource_data: Dict[str, Any]) -> Dict[str, Any]:
        # Calculate transparent pricing-derived estimate
        estimate = self.pricing_estimator.estimate_cost(resource_type, resource_data)
        monthly_cost = estimate["monthly_cost"]
        
        # Calculate potential savings if cleaned up
        estimate["potential_monthly_savings"] = monthly_cost
        estimate["potential_annual_savings"] = round(monthly_cost * 12, 2)
        return estimate

    def get_account_billing_summary(self) -> Dict[str, Any]:
        if not self.ce_estimator:
            return {
                "total_monthly_spend": 0.0,
                "status": "billing_data_unavailable",
                "service_breakdown": {}
            }
        services = self.ce_estimator.get_service_costs()
        total = round(sum(services.values()), 2)
        return {
            "total_monthly_spend": total,
            "status": "available" if services else "permission_denied_or_empty",
            "service_breakdown": services
        }
