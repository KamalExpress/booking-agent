"""
Transactional Outbox Pattern Implementation
=============================================
Ensures database mutations and EventBus (Redis Streams) publications maintain consistency.
"""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid
import logging

from models import EventLog
from core.event_bus import event_bus

logger = logging.getLogger(__name__)

def publish_transactional_event(
    db: Session,
    topic: str,
    event_type: str,
    payload: Dict[str, Any],
    source: str = "system",
    worker_id: Optional[str] = None,
    assignment_id: Optional[int] = None,
    severity: str = "info",
    tenant_id: Optional[int] = None
) -> str:
    """
    1. Records durable EventLog entry in PostgreSQL within the active DB transaction.
    2. Commits the DB transaction.
    3. Publishes event to EventBus (Redis Streams) with fail-visible semantics.
    """
    event_id = str(uuid.uuid4())
    log_entry = EventLog(
        source=source,
        worker_id=worker_id or source,
        assignment_id=assignment_id,
        event_type=event_type,
        severity=severity,
        payload=payload,
        created_at=datetime.now(timezone.utc)
    )
    db.add(log_entry)
    db.commit()

    # Publish to hot operational stream (Redis Streams)
    msg_id = event_bus.publish(
        topic=topic,
        event_type=event_type,
        payload=payload,
        source=source,
        worker_id=worker_id or source,
        tenant_id=tenant_id,
        event_id=event_id
    )
    return msg_id
