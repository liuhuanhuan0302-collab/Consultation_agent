import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import OperationLog, TrackingEvent, User


def write_operation_log(
    db: Session,
    user: User | None,
    action: str,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        OperationLog(
            user_id=user.id if user else None,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
        )
    )


def write_tracking_event(
    db: Session,
    event_name: str,
    session_token: str | None = None,
    lead_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        TrackingEvent(
            session_token=session_token,
            lead_id=lead_id,
            event_name=event_name,
            metadata_json=json.dumps(metadata, ensure_ascii=False) if metadata else None,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
