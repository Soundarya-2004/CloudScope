import json
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from . import models

class AuditService:
    """
    Maintains an immutable, chronologically ordered audit trail of every agent action,
    AWS API call, approval decision, and execution event.
    """
    @staticmethod
    def record_event(
        db: Session,
        action: str,
        status: str, # SUCCESS, FAILED, BLOCKED, PENDING
        run_id: Optional[str] = None,
        user: str = "system",
        aws_account_id: Optional[str] = None,
        region: Optional[str] = None,
        resource_id: Optional[str] = None,
        reason: Optional[str] = None,
        duration_ms: int = 0,
        details: Optional[Dict[str, Any]] = None
    ) -> models.AuditEvent:
        event = models.AuditEvent(
            timestamp=datetime.datetime.utcnow(),
            run_id=run_id,
            user=user,
            aws_account_id=aws_account_id,
            region=region,
            resource_id=resource_id,
            action=action,
            status=status,
            reason=reason,
            duration_ms=duration_ms,
            details_json=json.dumps(details) if details else None
        )
        db.add(event)
        db.commit()
        return event

    @staticmethod
    def get_events(
        db: Session,
        run_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100
    ) -> List[models.AuditEvent]:
        query = db.query(models.AuditEvent)
        if run_id:
            query = query.filter(models.AuditEvent.run_id == run_id)
        if resource_id:
            query = query.filter(models.AuditEvent.resource_id == resource_id)
        if action:
            query = query.filter(models.AuditEvent.action == action)
        return query.order_by(models.AuditEvent.timestamp.desc()).limit(limit).all()
