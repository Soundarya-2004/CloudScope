import pytest
import datetime
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app import models
from backend.app.approval_service import ApprovalService, compute_plan_hash

# Use in-memory SQLite for isolated, fast, robust tests
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_no_approval_blocks_destructive_action(db_session):
    """Attempting execution without an approval record must be immediately BLOCKED"""
    mock_aws_session = MagicMock()
    result = ApprovalService.validate_and_execute_approved_action(
        db=db_session,
        approval_id="non-existent-approval-id",
        session=mock_aws_session,
        current_plan_hash="any-hash"
    )
    assert result["success"] is False
    assert result["status"] == "BLOCKED"
    assert "not found" in result["error"].lower()

def test_pending_approval_blocks_destructive_action(db_session):
    """An approval in PENDING status must strictly BLOCK execution"""
    plan_hash = "valid-plan-hash-12345"
    req = models.ApprovalRequest(
        id="app-1",
        run_id="run-1",
        plan_id="plan-1",
        aws_account_id="123456789012",
        region="us-east-1",
        resource_id="i-0abcdef123456",
        resource_type="ec2",
        action="terminate_ec2",
        plan_hash=plan_hash,
        status="PENDING",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    )
    db_session.add(req)
    db_session.commit()

    mock_aws_session = MagicMock()
    result = ApprovalService.validate_and_execute_approved_action(
        db=db_session,
        approval_id="app-1",
        session=mock_aws_session,
        current_plan_hash=plan_hash
    )
    assert result["success"] is False
    assert result["status"] == "BLOCKED"
    assert "required: 'APPROVED'" in result["error"]

def test_rejected_approval_blocks_destructive_action(db_session):
    """An explicit REJECTED decision must strictly BLOCK execution"""
    plan_hash = "valid-plan-hash-12345"
    req = models.ApprovalRequest(
        id="app-rejected",
        run_id="run-1",
        plan_id="plan-1",
        aws_account_id="123456789012",
        region="us-east-1",
        resource_id="vol-0987654321",
        resource_type="ebs",
        action="delete_ebs",
        plan_hash=plan_hash,
        status="REJECTED",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    )
    db_session.add(req)
    db_session.commit()

    mock_aws_session = MagicMock()
    result = ApprovalService.validate_and_execute_approved_action(
        db=db_session,
        approval_id="app-rejected",
        session=mock_aws_session,
        current_plan_hash=plan_hash
    )
    assert result["success"] is False
    assert result["status"] == "BLOCKED"

def test_expired_approval_blocks_destructive_action(db_session):
    """An approval past its expiration timestamp must be marked EXPIRED and BLOCKED"""
    plan_hash = "valid-plan-hash-12345"
    past_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=10)
    req = models.ApprovalRequest(
        id="app-expired",
        run_id="run-1",
        plan_id="plan-1",
        aws_account_id="123456789012",
        region="us-east-1",
        resource_id="i-0abcdef123456",
        resource_type="ec2",
        action="terminate_ec2",
        plan_hash=plan_hash,
        status="APPROVED",
        expires_at=past_time
    )
    db_session.add(req)
    db_session.commit()

    mock_aws_session = MagicMock()
    result = ApprovalService.validate_and_execute_approved_action(
        db=db_session,
        approval_id="app-expired",
        session=mock_aws_session,
        current_plan_hash=plan_hash
    )
    assert result["success"] is False
    assert result["status"] == "EXPIRED"
    assert "expired" in result["error"].lower()

def test_altered_plan_hash_invalidates_previous_approval(db_session):
    """
    If the plan changes after approval (e.g. resource list altered),
    the old approval hash will not match current_plan_hash and must be INVALIDATED.
    """
    original_plan_hash = "original-hash-aaaa"
    altered_plan_hash = "altered-hash-bbbb"

    req = models.ApprovalRequest(
        id="app-altered",
        run_id="run-1",
        plan_id="plan-1",
        aws_account_id="123456789012",
        region="us-east-1",
        resource_id="i-0abcdef123456",
        resource_type="ec2",
        action="terminate_ec2",
        plan_hash=original_plan_hash,
        status="APPROVED",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    )
    db_session.add(req)
    db_session.commit()

    mock_aws_session = MagicMock()
    result = ApprovalService.validate_and_execute_approved_action(
        db=db_session,
        approval_id="app-altered",
        session=mock_aws_session,
        current_plan_hash=altered_plan_hash
    )
    assert result["success"] is False
    assert result["status"] == "INVALIDATED"
    assert "plan has changed" in result["error"].lower()

def test_plan_hash_calculation():
    """Verifies deterministic SHA-256 plan hash computation"""
    candidates_1 = [
        {"resource_id": "i-1", "resource_type": "ec2", "recommended_action": "terminate"},
        {"resource_id": "vol-1", "resource_type": "ebs", "recommended_action": "delete"}
    ]
    # Reverse order should produce identical hash due to sorting
    candidates_2 = [
        {"resource_id": "vol-1", "resource_type": "ebs", "recommended_action": "delete"},
        {"resource_id": "i-1", "resource_type": "ec2", "recommended_action": "terminate"}
    ]
    h1 = compute_plan_hash(candidates_1, "123456789012", "us-east-1")
    h2 = compute_plan_hash(candidates_2, "123456789012", "us-east-1")
    assert h1 == h2
    assert len(h1) == 64

def test_pre_deletion_check_fails_if_instance_already_terminated(db_session):
    """If live check reveals the instance is already terminating/terminated, execution must ABORT"""
    plan_hash = "valid-hash"
    req = models.ApprovalRequest(
        id="app-already-dead",
        run_id="run-1",
        plan_id="plan-1",
        aws_account_id="123456789012",
        region="us-east-1",
        resource_id="i-already-dead",
        resource_type="ec2",
        action="terminate_ec2",
        plan_hash=plan_hash,
        status="APPROVED",
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    )
    db_session.add(req)
    db_session.commit()

    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    mock_ec2.describe_instances.return_value = {
        "Reservations": [{"Instances": [{"State": {"Name": "terminated"}}]}]
    }
    mock_session.client.return_value = mock_ec2

    result = ApprovalService.validate_and_execute_approved_action(
        db=db_session,
        approval_id="app-already-dead",
        session=mock_session,
        current_plan_hash=plan_hash
    )
    assert result["success"] is False
    assert result["status"] == "FAILED"
    assert "already terminated" in result["error"].lower()

def test_direct_termination_executes_safely(db_session):
    """Direct component termination must verify state, execute via sandbox, and update DB"""
    # Create sample resource snapshot
    snap = models.ResourceSnapshot(
        run_id="run-1",
        resource_id="i-test-direct-terminate",
        resource_type="ec2",
        region="us-east-1",
        name="test-server",
        state="running",
        is_waste=True
    )
    db_session.add(snap)
    db_session.commit()

    mock_session = MagicMock()
    mock_ec2 = MagicMock()
    # First call (pre-check): running
    # Second call (post-check): terminating
    mock_ec2.describe_instances.side_effect = [
        {"Reservations": [{"Instances": [{"State": {"Name": "running"}}]}]},
        {"Reservations": [{"Instances": [{"State": {"Name": "terminating"}}]}]}
    ]
    mock_session.client.return_value = mock_ec2

    with patch("backend.app.approval_service.sandbox.execute_python_code") as mock_sandbox:
        mock_sandbox.return_value = {"success": True, "output": "Instance terminating", "duration_ms": 150}

        result = ApprovalService.execute_direct_termination(
            db=db_session,
            session=mock_session,
            resource_id="i-test-direct-terminate",
            resource_type="ec2",
            region="us-east-1",
            user_id="admin",
            reason="User clicked delete button"
        )

        assert result["success"] is True
        assert result["status"] == "COMPLETED"
        assert "terminating" in result["message"]

        # Check DB update
        updated_snap = db_session.query(models.ResourceSnapshot).filter(models.ResourceSnapshot.resource_id == "i-test-direct-terminate").first()
        assert updated_snap.state == "terminated"
        assert updated_snap.is_waste is False

def test_lambda_pre_check_and_code_generation():
    """ApprovalService must support Lambda pre-checks and code generation"""
    mock_session = MagicMock()
    mock_lambda = MagicMock()
    mock_lambda.get_function.return_value = {"Configuration": {"FunctionName": "old-func"}}
    mock_session.client.return_value = mock_lambda

    passed, msg = ApprovalService._pre_execution_safety_check(mock_session, "lambda", "old-func")
    assert passed is True
    assert "old-func exists" in msg

    code = ApprovalService._generate_cleanup_code("lambda", "old-func", "us-east-1")
    assert "delete_function" in code
    assert "old-func" in code

def test_s3_pre_check_and_code_generation():
    """ApprovalService must support S3 bucket pre-checks and code generation"""
    mock_session = MagicMock()
    mock_s3 = MagicMock()
    mock_s3.head_bucket.return_value = {}
    mock_session.client.return_value = mock_s3

    passed, msg = ApprovalService._pre_execution_safety_check(mock_session, "s3", "my-empty-bucket")
    assert passed is True
    assert "my-empty-bucket exists" in msg

    code = ApprovalService._generate_cleanup_code("s3", "my-empty-bucket", "us-east-1")
    assert "delete_bucket" in code
    assert "my-empty-bucket" in code
