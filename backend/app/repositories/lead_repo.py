"""Admin lead-management queries and audit persistence."""

import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.audit import ExportLog
from app.models.export_batch import ExportBatch
from app.models.lead import CompanyLead
from app.models.report import AiConversationMessage, Report, ReportDeliveryJob, ReportDeliveryStatus
from app.repositories.consult_repo import latest_submission_for_lead as _latest_submission_for_lead


def get_lead_by_id(db: Session, lead_id: int) -> CompanyLead | None:
    return db.query(CompanyLead).filter(CompanyLead.id == lead_id).first()


def get_report_by_id(db: Session, report_id: int) -> Report | None:
    return db.query(Report).filter(Report.id == report_id).first()


def latest_submission_for_lead(db: Session, lead_id: int):
    """Preserve the existing definition of latest: greatest submission id."""
    return _latest_submission_for_lead(db, lead_id)


def latest_delivery_for_report(db: Session, report_id: int) -> ReportDeliveryJob | None:
    return (
        db.query(ReportDeliveryJob)
        .filter(ReportDeliveryJob.report_id == report_id)
        .order_by(ReportDeliveryJob.created_at.desc())
        .first()
    )


def latest_sent_delivery_for_report(db: Session, report_id: int) -> ReportDeliveryJob | None:
    return (
        db.query(ReportDeliveryJob)
        .filter(
            ReportDeliveryJob.report_id == report_id,
            ReportDeliveryJob.status == ReportDeliveryStatus.sent.value,
        )
        .order_by(ReportDeliveryJob.sent_at.desc(), ReportDeliveryJob.id.desc())
        .first()
    )


def queued_delivery_position(db: Session, delivery_id: int) -> int:
    ahead = (
        db.query(func.count(ReportDeliveryJob.id))
        .filter(
            ReportDeliveryJob.status == ReportDeliveryStatus.queued.value,
            ReportDeliveryJob.id < delivery_id,
        )
        .scalar()
        or 0
    )
    return ahead + 1


def advisor_messages_for_report(db: Session, report_id: int) -> list[AiConversationMessage]:
    return (
        db.query(AiConversationMessage)
        .filter(AiConversationMessage.report_id == report_id)
        .order_by(AiConversationMessage.created_at.asc())
        .all()
    )


def list_export_batches(db: Session, limit: int = 100) -> list["ExportBatch"]:
    return db.query(ExportBatch).order_by(ExportBatch.created_at.desc(), ExportBatch.id.desc()).limit(limit).all()


def get_export_batch(db: Session, batch_id: int) -> ExportBatch | None:
    return db.query(ExportBatch).filter(ExportBatch.id == batch_id).first()


def add_export_log(
    db: Session,
    *,
    user_id: int,
    export_type: str,
    rows_count: int,
    filters: dict | None = None,
) -> None:
    db.add(
        ExportLog(
            user_id=user_id,
            export_type=export_type,
            filters_json=json.dumps(filters) if filters is not None else None,
            rows_count=rows_count,
        )
    )
