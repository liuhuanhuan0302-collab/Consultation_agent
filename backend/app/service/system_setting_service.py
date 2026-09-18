"""Business rules for report contact settings and immutable report snapshots."""

from sqlalchemy.orm import Session

from app.models.system_setting import ReportContactSetting, ReportQueueSetting
from app.models.user import User
from app.models.report import ReportDeliveryStatus, ReportQueueState
from app.repositories import report_queue_repo
from app.repositories.system_setting_repo import create_report_contact_settings, get_report_contact_settings
from app.schemas.system_setting import ReportContactSettingsUpdate, ReportQueueSettingsUpdate
from app.service import report_queue_scheduler
from app.utils.logging_utils import write_operation_log


REPORT_CONTACT_FIELDS = ("contact_name", "phone", "wechat", "email")


def load_report_contact_settings(db: Session) -> ReportContactSetting:
    settings = get_report_contact_settings(db)
    # Reads must not create database state. The singleton is persisted only when
    # an administrator saves it; until then callers receive empty defaults.
    return settings if settings is not None else ReportContactSetting(
        id=1,
        contact_name="",
        phone="",
        wechat="",
        email="",
    )


def update_report_contact_settings(
    db: Session,
    payload: ReportContactSettingsUpdate,
    *,
    updated_by: str,
) -> ReportContactSetting:
    settings = get_report_contact_settings(db)
    if settings is None:
        settings = create_report_contact_settings(db)
    for field in REPORT_CONTACT_FIELDS:
        setattr(settings, field, str(getattr(payload, field) or "").strip())
    settings.updated_by = updated_by
    db.commit()
    db.refresh(settings)
    return settings


def report_contact_snapshot(db: Session) -> dict[str, str]:
    """Return only populated values for persistence inside one report summary."""

    settings = load_report_contact_settings(db)
    return {
        field: value
        for field in REPORT_CONTACT_FIELDS
        if (value := str(getattr(settings, field, "") or "").strip())
    }


def load_report_queue_overview(db: Session) -> dict:
    settings = report_queue_scheduler.load_queue_settings(db)
    queue_counts = {state.value: 0 for state in ReportQueueState}
    queue_counts.update(report_queue_repo.grouped_queue_state_counts(db))
    lifecycle_counts = {status.value: 0 for status in ReportDeliveryStatus}
    lifecycle_counts.update(report_queue_repo.grouped_lifecycle_counts(db))
    known_stages = ("initializing", "research", "report", "waiting_pdf", "pdf", "email")
    stage_counts = {stage: 0 for stage in known_stages}
    stage_counts.update(report_queue_repo.grouped_processing_stage_counts(db))
    durations = report_queue_repo.list_recent_completed_durations(db)
    drainable = queue_counts[ReportQueueState.active.value] + queue_counts[ReportQueueState.automatic_waiting.value] + queue_counts[ReportQueueState.approved_waiting.value]
    eta = None
    if drainable == 0:
        eta = 0.0
    elif durations and not settings.processing_paused:
        average_seconds = sum(durations) / len(durations)
        eta = round(average_seconds * drainable / max(settings.processing_concurrency, 1) / 60, 1)
    manual_jobs = []
    for job, company_name, report_title in report_queue_repo.list_manual_review_rows(db):
        manual_jobs.append({
            "id": job.id,
            "lead_id": job.lead_id,
            "company_name": company_name or "未填写公司",
            "report_id": job.report_id,
            "report_title": report_title,
            "task_kind": str(job.task_kind),
            "status": str(job.status),
            "queue_state": str(job.queue_state),
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
            "last_error": job.last_error,
            "approved_at": job.approved_at,
            "approved_by": job.approved_by,
            "created_at": job.created_at,
        })
    return {
        "settings": settings,
        "queue_state_counts": queue_counts,
        "lifecycle_counts": lifecycle_counts,
        "processing_stage_counts": stage_counts,
        "approximate_drain_minutes": eta,
        "eta_basis_completed_jobs": len(durations),
        "manual_review_jobs": manual_jobs,
    }


def update_report_queue_settings(db: Session, payload: ReportQueueSettingsUpdate, *, user: User) -> ReportQueueSetting:
    old = report_queue_scheduler.load_queue_settings(db)
    old_values = {field: getattr(old, field) for field in report_queue_scheduler.SETTING_FIELDS}
    try:
        settings = report_queue_scheduler.update_queue_settings(
            db,
            updated_by=user.email,
            confirm_processing_increase=payload.confirm_processing_increase,
            commit=False,
            **payload.model_dump(exclude={"confirm_processing_increase"}),
        )
        new_values = {field: getattr(settings, field) for field in report_queue_scheduler.SETTING_FIELDS}
        write_operation_log(db, user, "update_report_queue_settings", "report_queue_settings", 1, {"before": old_values, "after": new_values})
        db.commit()
        db.refresh(settings)
        return settings
    except Exception:
        db.rollback()
        raise


def approve_report_queue_jobs(db: Session, job_ids: list[int], *, user: User) -> list[int]:
    try:
        jobs = report_queue_scheduler.approve_manual_jobs(db, job_ids, approved_by=user.email, commit=False)
        affected = [job.id for job in jobs]
        write_operation_log(db, user, "approve_report_queue_jobs", "report_queue_jobs", "batch", {"job_ids": affected})
        db.commit()
        return affected
    except Exception:
        db.rollback()
        raise


def reject_report_queue_jobs(db: Session, job_ids: list[int], *, user: User, reason: str | None) -> list[int]:
    try:
        jobs = report_queue_scheduler.reject_review_jobs(db, job_ids, rejected_by=user.email, reason=reason, commit=False)
        affected = [job.id for job in jobs]
        write_operation_log(db, user, "reject_report_queue_jobs", "report_queue_jobs", "batch", {"job_ids": affected, "reason": (reason or "").strip()})
        db.commit()
        return affected
    except Exception:
        db.rollback()
        raise
