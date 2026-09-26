import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app.audit_service import AuditService
from backend.app.notification_service import NotificationService

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_audit_event_recording(db):
    event = AuditService.record_event(
        db,
        action="APPROVAL_REQUESTED",
        status="PENDING",
        run_id="run-test",
        user="test-engineer",
        resource_id="i-test123",
        reason="Human approval required for termination",
        details={"cost": 18.40}
    )
    assert event.id is not None
    assert event.action == "APPROVAL_REQUESTED"

    events = AuditService.get_events(db, run_id="run-test")
    assert len(events) == 1
    assert events[0].resource_id == "i-test123"

def test_notification_creation(db):
    notif = NotificationService.record_and_dispatch_notification(
        db=db,
        notif_type="approval_required",
        title="Approval Required",
        message="EC2 instance i-test123 requires approval",
        link="/approvals"
    )
    assert notif.id is not None
    assert notif.is_read is False
    assert notif.type == "approval_required"
