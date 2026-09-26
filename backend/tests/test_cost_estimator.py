import pytest
from backend.app.cost_engine import (
    ResourcePricingEstimator,
    CompositeCostEstimator,
    EC2_HOURLY_RATES,
    EBS_PER_GB_MONTHLY_RATES,
    ELB_HOURLY_BASELINE,
    HOURS_PER_MONTH
)

def test_ec2_cost_estimation():
    estimator = ResourcePricingEstimator()
    res = estimator.estimate_cost("ec2", {"instance_type": "t3.medium", "state": "running"})
    expected = round(EC2_HOURLY_RATES["t3.medium"] * HOURS_PER_MONTH, 2)
    assert res["monthly_cost"] == expected
    assert res["cost_source"] == "aws_pricing_derived"
    assert res["confidence"] == "high"
    assert "t3.medium" in res["calculation_method"]

def test_ec2_stopped_cost_is_zero_compute():
    estimator = ResourcePricingEstimator()
    res = estimator.estimate_cost("ec2", {"instance_type": "t3.large", "state": "stopped"})
    assert res["monthly_cost"] == 0.0
    assert "Stopped EC2" in res["calculation_method"]

def test_ebs_volume_cost_estimation():
    estimator = ResourcePricingEstimator()
    res = estimator.estimate_cost("ebs", {"size": 100, "volume_type": "gp3"})
    expected = round(100 * EBS_PER_GB_MONTHLY_RATES["gp3"], 2)
    assert res["monthly_cost"] == expected
    assert res["cost_source"] == "aws_pricing_derived"
    assert "100" in res["calculation_method"]

def test_elb_cost_estimation():
    estimator = ResourcePricingEstimator()
    res = estimator.estimate_cost("elb", {"type": "application"})
    expected = round(ELB_HOURLY_BASELINE * HOURS_PER_MONTH, 2)
    assert res["monthly_cost"] == expected
    assert res["cost_source"] == "aws_pricing_derived"

def test_composite_estimator_savings_calculation():
    comp = CompositeCostEstimator(session=None)
    est = comp.estimate_resource_cost("ebs", {"size": 200, "volume_type": "gp3"})
    assert est["potential_monthly_savings"] == est["monthly_cost"]
    assert est["potential_annual_savings"] == round(est["monthly_cost"] * 12, 2)
