import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.main import app
from backend.app.database import Base, get_db
from backend.app import models, auth

from sqlalchemy.pool import StaticPool

# Test SQLite DB configured for multi-threaded FastAPI tests
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def override_get_current_user():
    return models.User(id=1, username="test-admin", role="Admin")

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[auth.get_current_user] = override_get_current_user

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def client():
    return TestClient(app)

def test_direct_resource_delete_requires_confirmation(client):
    """Direct deletion must be blocked if confirmation is False"""
    response = client.post(
        "/api/resources/i-12345/delete",
        json={"resource_type": "ec2", "confirmation": False}
    )
    assert response.status_code == 400
    assert "confirmation checkbox is required" in response.json()["detail"].lower()

def test_direct_resource_delete_executes_safely(client):
    """Direct component deletion executes pre-check, sandbox, and returns success"""
    db = TestingSessionLocal()
    # Add snapshot
    snap = models.ResourceSnapshot(
        run_id="run-1",
        resource_id="i-test-delete",
        resource_type="ec2",
        region="us-east-1",
        name="idle-worker",
        state="running",
        is_waste=True
    )
    db.add(snap)
    db.commit()
    db.close()

    mock_session = MagicMock()
    mock_meta = {"is_authenticated": True, "account_id": "123456789012", "region": "us-east-1", "arn": "arn:aws:iam::123:user/test"}

    with patch("backend.app.routes.resolve_aws_session", return_value=(mock_session, mock_meta)), \
         patch("backend.app.approval_service.ApprovalService._pre_execution_safety_check", return_value=(True, "Verified running")), \
         patch("backend.app.approval_service.sandbox.execute_python_code", return_value={"success": True, "output": "Terminating", "duration_ms": 120}), \
         patch("backend.app.approval_service.ApprovalService._post_execution_verification", return_value=(True, "Verified terminating")):

        response = client.post(
            "/api/resources/i-test-delete/delete",
            json={"resource_type": "ec2", "region": "us-east-1", "confirmation": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "COMPLETED"

def test_auto_terminate_on_approval(client):
    """When an approval is granted with auto_execute=True, it executes termination automatically"""
    db = TestingSessionLocal()
    plan_hash = "test-hash-123"
    req = models.ApprovalRequest(
        id="app-auto-exec",
        run_id="run-1",
        plan_id="plan-1",
        aws_account_id="123456789012",
        region="us-east-1",
        resource_id="vol-test-auto",
        resource_type="ebs",
        resource_name="orphaned-vol",
        action="delete_ebs",
        plan_hash=plan_hash,
        status="PENDING",
        expires_at=models.datetime.datetime.utcnow() + models.datetime.timedelta(hours=2)
    )
    db.add(req)
    db.commit()
    db.close()

    mock_session = MagicMock()
    mock_meta = {"is_authenticated": True, "account_id": "123456789012", "region": "us-east-1", "arn": "arn:aws:iam::123:user/test"}

    with patch("backend.app.routes.resolve_aws_session", return_value=(mock_session, mock_meta)), \
         patch("backend.app.approval_service.ApprovalService._pre_execution_safety_check", return_value=(True, "Verified available")), \
         patch("backend.app.approval_service.sandbox.execute_python_code", return_value={"success": True, "output": "Deleted volume", "duration_ms": 110}), \
         patch("backend.app.approval_service.ApprovalService._post_execution_verification", return_value=(True, "Verified volume deleted")):

        response = client.post(
            "/api/approvals/app-auto-exec/approve",
            json={"reason": "User granted permission with auto-terminate", "auto_execute": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "COMPLETED"
        assert "auto-terminated" in data["message"].lower()
