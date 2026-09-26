import pytest
from unittest.mock import MagicMock
from backend.app.analyzers.ec2_analyzer import IdleEC2Analyzer
from backend.app.analyzers.ebs_analyzer import OrphanedEBSAnalyzer
from backend.app.analyzers.elb_analyzer import UnusedLoadBalancerAnalyzer
from backend.app.cost_engine import CompositeCostEstimator

def test_unattached_ebs_volume_detected_as_orphaned():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-orphan123",
                "State": "available", # unattached
                "Size": 80,
                "VolumeType": "gp3",
                "Attachments": [],
                "Tags": [{"Key": "Name", "Value": "test-data"}]
            }
        ]
    }
    mock_session.client.return_value = mock_ec2
    mock_session.region_name = "us-east-1"

    cost_est = CompositeCostEstimator(mock_session)
    analyzer = OrphanedEBSAnalyzer(mock_session, cost_est)
    candidates = analyzer.analyze_volumes()

    assert len(candidates) == 1
    c = candidates[0]
    assert c["resource_id"] == "vol-orphan123"
    assert c["is_waste"] is True
    assert c["waste_finding"] == "likely_orphaned"
    assert c["recommended_action"] == "delete"
    assert c["requires_approval"] is True
    assert c["monthly_cost"] > 0

def test_attached_ebs_volume_is_not_waste():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_ec2.describe_volumes.return_value = {
        "Volumes": [
            {
                "VolumeId": "vol-inuse456",
                "State": "in-use",
                "Size": 50,
                "VolumeType": "gp3",
                "Attachments": [{"InstanceId": "i-12345", "Device": "/dev/sda1"}],
                "Tags": []
            }
        ]
    }
    mock_session.client.return_value = mock_ec2
    mock_session.region_name = "us-east-1"

    cost_est = CompositeCostEstimator(mock_session)
    analyzer = OrphanedEBSAnalyzer(mock_session, cost_est)
    candidates = analyzer.analyze_volumes()

    assert len(candidates) == 1
    assert candidates[0]["is_waste"] is False
    assert candidates[0]["recommended_action"] == "retain"

def test_load_balancer_with_zero_target_groups_is_waste():
    mock_session = MagicMock()
    mock_elbv2 = MagicMock()
    mock_elbv2.describe_load_balancers.return_value = {
        "LoadBalancers": [
            {
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/idle-alb/123",
                "LoadBalancerName": "idle-alb",
                "Type": "application",
                "State": {"Code": "active"},
                "Scheme": "internet-facing"
            }
        ]
    }
    mock_elbv2.describe_target_groups.return_value = {"TargetGroups": []}
    mock_elbv2.describe_listeners.return_value = {"Listeners": []}
    mock_session.client.return_value = mock_elbv2
    mock_session.region_name = "us-east-1"

    cost_est = CompositeCostEstimator(mock_session)
    analyzer = UnusedLoadBalancerAnalyzer(mock_session, cost_est)
    candidates = analyzer.analyze_load_balancers()

    assert len(candidates) == 1
    c = candidates[0]
    assert c["is_waste"] is True
    assert c["waste_finding"] == "unused_load_balancer"
    assert c["recommended_action"] == "delete"
    assert c["requires_approval"] is True
