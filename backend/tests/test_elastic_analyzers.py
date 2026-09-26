import pytest
from unittest.mock import MagicMock
from backend.app.analyzers.elastic_ip_analyzer import UnattachedElasticIPAnalyzer
from backend.app.analyzers.nat_gateway_analyzer import IdleNATGatewayAnalyzer
from backend.app.analyzers.rds_analyzer import RDSAnalyzer
from backend.app.analyzers.lambda_analyzer import LambdaAnalyzer
from backend.app.analyzers.global_resource_scanner import GlobalResourceScanner
from backend.app.cost_engine import CompositeCostEstimator

def test_unattached_elastic_ip_detected():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_ec2.describe_addresses.return_value = {
        "Addresses": [
            {
                "PublicIp": "54.12.34.56",
                "AllocationId": "eipalloc-0123456789",
                "AssociationId": None,
                "InstanceId": None,
                "Tags": [{"Key": "Name", "Value": "orphaned-ip"}]
            }
        ]
    }
    mock_session.client.return_value = mock_ec2
    mock_session.region_name = "us-east-1"

    cost_est = CompositeCostEstimator(mock_session)
    analyzer = UnattachedElasticIPAnalyzer(mock_session, cost_est)
    cands = analyzer.analyze_eips()

    assert len(cands) == 1
    c = cands[0]
    assert c["is_waste"] is True
    assert c["waste_finding"] == "unattached_elastic_ip"
    assert c["recommended_action"] == "release"
    assert c["requires_approval"] is True
    assert c["monthly_cost"] > 0

def test_attached_elastic_ip_not_waste():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_ec2.describe_addresses.return_value = {
        "Addresses": [
            {
                "PublicIp": "54.99.88.77",
                "AllocationId": "eipalloc-attached",
                "AssociationId": "eipassoc-12345",
                "InstanceId": "i-running123",
                "Tags": []
            }
        ]
    }
    mock_session.client.return_value = mock_ec2
    mock_session.region_name = "us-east-1"

    cost_est = CompositeCostEstimator(mock_session)
    analyzer = UnattachedElasticIPAnalyzer(mock_session, cost_est)
    cands = analyzer.analyze_eips()

    assert len(cands) == 1
    assert cands[0]["is_waste"] is False
    assert cands[0]["monthly_cost"] == 0.0

def test_nat_gateway_provisioning_cost():
    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_ec2.describe_nat_gateways.return_value = {
        "NatGateways": [
            {
                "NatGatewayId": "nat-0123456",
                "VpcId": "vpc-09876",
                "State": "available",
                "Tags": []
            }
        ]
    }
    mock_session.client.return_value = mock_ec2
    mock_session.region_name = "us-east-1"

    cost_est = CompositeCostEstimator(mock_session)
    analyzer = IdleNATGatewayAnalyzer(mock_session, cost_est)
    cands = analyzer.analyze_nat_gateways()

    assert len(cands) == 1
    assert cands[0]["monthly_cost"] > 30.0

def test_stopped_rds_database_detected():
    mock_session = MagicMock()
    mock_rds = MagicMock()
    mock_rds.describe_db_instances.return_value = {
        "DBInstances": [
            {
                "DBInstanceIdentifier": "dev-analytics-db",
                "Engine": "postgres",
                "DBInstanceClass": "db.t3.medium",
                "DBInstanceStatus": "stopped",
                "AllocatedStorage": 100,
                "TagList": []
            }
        ]
    }
    mock_session.client.return_value = mock_rds
    mock_session.region_name = "us-east-1"

    cost_est = CompositeCostEstimator(mock_session)
    analyzer = RDSAnalyzer(mock_session, cost_est)
    cands = analyzer.analyze_databases()

    assert len(cands) == 1
    c = cands[0]
    assert c["is_waste"] is True
    assert c["state"] == "stopped"

def test_deprecated_lambda_runtime_flagged():
    mock_session = MagicMock()
    mock_lambda = MagicMock()
    mock_lambda.list_functions.return_value = {
        "Functions": [
            {
                "FunctionName": "legacy-auth-function",
                "Runtime": "python3.7",
                "CodeSize": 500000,
                "LastModified": "2021-01-01T00:00:00Z",
                "FunctionArn": "arn:aws:lambda:us-east-1:12345:function:legacy-auth-function"
            }
        ]
    }
    mock_session.client.return_value = mock_lambda
    mock_session.region_name = "us-east-1"

    cost_est = CompositeCostEstimator(mock_session)
    analyzer = LambdaAnalyzer(mock_session, cost_est)
    cands = analyzer.analyze_functions()

    assert len(cands) == 1
    assert cands[0]["is_waste"] is True
    assert cands[0]["waste_finding"] == "deprecated_runtime"

def test_global_resource_scanner_dynamic_discovery():
    mock_session = MagicMock()
    mock_tagging = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "ResourceTagMappingList": [
                {
                    "ResourceARN": "arn:aws:dynamodb:us-east-1:123456789012:table/UserSessions",
                    "Tags": [] # untagged
                },
                {
                    "ResourceARN": "arn:aws:elasticache:us-east-1:123456789012:cluster/redis-cache",
                    "Tags": [{"Key": "Environment", "Value": "production"}]
                }
            ]
        }
    ]
    mock_tagging.get_paginator.return_value = mock_paginator
    mock_session.client.return_value = mock_tagging
    mock_session.region_name = "us-east-1"

    cost_est = CompositeCostEstimator(mock_session)
    scanner = GlobalResourceScanner(mock_session, cost_est)
    results = scanner.scan_all_services(already_discovered_ids=set())

    assert len(results) == 2
    # DynamoDB table without tags flagged for review
    dynamo = next(r for r in results if r["resource_type"] == "dynamodb")
    assert dynamo["is_waste"] is True
    assert dynamo["waste_finding"] == "untagged_unmanaged_resource"
