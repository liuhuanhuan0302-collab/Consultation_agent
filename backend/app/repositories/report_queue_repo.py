"""Persistence operations for the database-backed report queue scheduler."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.report import ReportDeliveryJob, ReportDeliveryStatus, ReportQueueState
from app.models.lead import CompanyLead
from app.models.report import Report


def get_delivery_job_for_update(db: Session, job_id: int) -> ReportDeliveryJob | None:
    return (
        db.query(ReportDeliveryJob)
        .filter(ReportDeliveryJob.id == job_id)
        .with_for_update()
        .populate_existing()
        .first()
    )


def get_delivery_jobs_for_update(db: Session, job_ids: list[int]) -> list[ReportDeliveryJob]:
    if not job_ids:
        return []
    return (
        db.query(ReportDeliveryJob)
        .filter(ReportDeliveryJob.id.in_(job_ids))
        .order_by(ReportDeliveryJob.id.asc())
        .with_for_update()
        .populate_existing()
        .all()
    )


def count_jobs_in_state(db: Session, state: ReportQueueState | str) -> int:
    value = state.value if isinstance(state, ReportQueueState) else state
    return (
        db.query(func.count(ReportDeliveryJob.id))
        .filter(
            ReportDeliveryJob.queue_state == value,
            ReportDeliveryJob.status.in_(
                (ReportDeliveryStatus.queued.value, ReportDeliveryStatus.processing.value)
            ),
        )
        .scalar()
        or 0
    )


def list_waiting_jobs_for_update(
    db: Session,
    state: ReportQueueState | str,
    *,
    limit: int,
) -> list[ReportDeliveryJob]:
    if limit <= 0:
        return []
    value = state.value if isinstance(state, ReportQueueState) else state
    ordering = (
        (
            ReportDeliveryJob.approved_at.asc(),
            ReportDeliveryJob.created_at.asc(),
            ReportDeliveryJob.id.asc(),
        )
        if value == ReportQueueState.approved_waiting.value
        else (ReportDeliveryJob.created_at.asc(), ReportDeliveryJob.id.asc())
    )
    return (
        db.query(ReportDeliveryJob)
        .filter(
            ReportDeliveryJob.queue_state == value,
            ReportDeliveryJob.status == ReportDeliveryStatus.queued.value,
        )
        .order_by(*ordering)
        .limit(limit)
        .with_for_update()
        .all()
    )


def assign_queue_state(job: ReportDeliveryJob, state: ReportQueueState | None) -> None:
    job.queue_state = state.value if state is not None else None


def count_processing_jobs(db: Session) -> int:
    return (
        db.query(func.count(ReportDeliveryJob.id))
        .filter(ReportDeliveryJob.status == ReportDeliveryStatus.processing.value)
        .scalar()
        or 0
    )


def count_pdf_jobs(db: Session) -> int:
    return (
        db.query(func.count(ReportDeliveryJob.id))
        .filter(
            ReportDeliveryJob.status == ReportDeliveryStatus.processing.value,
            ReportDeliveryJob.processing_stage == "pdf",
        )
        .scalar()
        or 0
    )


def next_claimable_active_job_for_update(
    db: Session,
    *,
    at: datetime,
) -> ReportDeliveryJob | None:
    return (
        db.query(ReportDeliveryJob)
        .filter(
            ReportDeliveryJob.queue_state == ReportQueueState.active.value,
            ReportDeliveryJob.status == ReportDeliveryStatus.queued.value,
            ReportDeliveryJob.run_after <= at,
            ReportDeliveryJob.attempts < ReportDeliveryJob.max_attempts,
        )
        .order_by(ReportDeliveryJob.run_after.asc(), ReportDeliveryJob.created_at.asc(), ReportDeliveryJob.id.asc())
        .with_for_update()
        .first()
    )


def grouped_queue_state_counts(db: Session) -> dict[str, int]:
    return {
        str(state): int(count)
        for state, count in db.query(ReportDeliveryJob.queue_state, func.count(ReportDeliveryJob.id))
        .filter(ReportDeliveryJob.queue_state.is_not(None))
        .group_by(ReportDeliveryJob.queue_state)
        .all()
    }


def grouped_lifecycle_counts(db: Session) -> dict[str, int]:
    return {
        str(status): int(count)
        for status, count in db.query(ReportDeliveryJob.status, func.count(ReportDeliveryJob.id))
        .group_by(ReportDeliveryJob.status)
        .all()
    }


def grouped_processing_stage_counts(db: Session) -> dict[str, int]:
    return {
        str(stage): int(count)
        for stage, count in db.query(ReportDeliveryJob.processing_stage, func.count(ReportDeliveryJob.id))
        .filter(
            ReportDeliveryJob.status == ReportDeliveryStatus.processing.value,
            ReportDeliveryJob.processing_stage.is_not(None),
        )
        .group_by(ReportDeliveryJob.processing_stage)
        .all()
    }


def list_manual_review_rows(db: Session, *, limit: int = 200) -> list[tuple[ReportDeliveryJob, str | None, str]]:
    return (
        db.query(ReportDeliveryJob, CompanyLead.company_name, Report.title)
        .join(CompanyLead, CompanyLead.id == ReportDeliveryJob.lead_id)
        .join(Report, Report.id == ReportDeliveryJob.report_id)
        .filter(ReportDeliveryJob.queue_state == ReportQueueState.manual_review.value)
        .order_by(ReportDeliveryJob.created_at.asc(), ReportDeliveryJob.id.asc())
        .limit(limit)
        .all()
    )


def list_recent_completed_durations(db: Session, *, limit: int = 50) -> list[float]:
    jobs = (
        db.query(ReportDeliveryJob)
        .filter(
            ReportDeliveryJob.status == ReportDeliveryStatus.sent.value,
            ReportDeliveryJob.sent_at.is_not(None),
        )
        .order_by(ReportDeliveryJob.sent_at.desc(), ReportDeliveryJob.id.desc())
        .limit(limit)
        .all()
    )
    return [
        (job.sent_at - job.created_at).total_seconds()
        for job in jobs
        if job.sent_at is not None and job.created_at is not None and job.sent_at > job.created_at
    ]
