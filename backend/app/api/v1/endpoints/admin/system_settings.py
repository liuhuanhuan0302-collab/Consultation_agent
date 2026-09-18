"""Administrator-only global report settings endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.system_setting import ReportContactSettingsRead, ReportContactSettingsUpdate, ReportQueueActionRequest, ReportQueueActionResponse, ReportQueueOverviewRead, ReportQueueSettingsRead, ReportQueueSettingsUpdate
from app.service import report_queue_scheduler
from app.service.system_setting_service import approve_report_queue_jobs, load_report_contact_settings, load_report_queue_overview, reject_report_queue_jobs, update_report_contact_settings, update_report_queue_settings
from app.utils.auth import AdminOnly


router = APIRouter()


@router.get("/api/admin/system-settings/report-contact", response_model=ReportContactSettingsRead)
def get_report_contact_settings(
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> ReportContactSettingsRead:
    return ReportContactSettingsRead.model_validate(load_report_contact_settings(db))


@router.put("/api/admin/system-settings/report-contact", response_model=ReportContactSettingsRead)
def put_report_contact_settings(
    payload: ReportContactSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(AdminOnly),
) -> ReportContactSettingsRead:
    settings = update_report_contact_settings(db, payload, updated_by=user.email)
    return ReportContactSettingsRead.model_validate(settings)


@router.get("/api/admin/system-settings/report-queue", response_model=ReportQueueSettingsRead)
def get_report_queue_settings(db: Session = Depends(get_db), user: User = Depends(AdminOnly)):
    return ReportQueueSettingsRead.model_validate(report_queue_scheduler.load_queue_settings(db))


@router.put("/api/admin/system-settings/report-queue", response_model=ReportQueueSettingsRead)
def put_report_queue_settings(payload: ReportQueueSettingsUpdate, db: Session = Depends(get_db), user: User = Depends(AdminOnly)):
    try:
        return ReportQueueSettingsRead.model_validate(update_report_queue_settings(db, payload, user=user))
    except report_queue_scheduler.ReportQueueConfirmationRequiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except report_queue_scheduler.ReportQueueSettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/api/admin/system-settings/report-queue/overview", response_model=ReportQueueOverviewRead)
def get_report_queue_overview(db: Session = Depends(get_db), user: User = Depends(AdminOnly)):
    return ReportQueueOverviewRead.model_validate(load_report_queue_overview(db))


def _queue_action_error(exc: Exception) -> HTTPException:
    if isinstance(exc, report_queue_scheduler.ReportQueueJobNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=409, detail=str(exc))


@router.post("/api/admin/system-settings/report-queue/approve", response_model=ReportQueueActionResponse)
def approve_queue_jobs(payload: ReportQueueActionRequest, db: Session = Depends(get_db), user: User = Depends(AdminOnly)):
    try:
        affected = approve_report_queue_jobs(db, payload.job_ids, user=user)
    except report_queue_scheduler.ReportQueueSchedulerError as exc:
        raise _queue_action_error(exc) from exc
    return ReportQueueActionResponse(affected_job_ids=affected, message=f"已批准 {len(affected)} 个任务")


@router.post("/api/admin/system-settings/report-queue/reject", response_model=ReportQueueActionResponse)
def reject_queue_jobs(payload: ReportQueueActionRequest, db: Session = Depends(get_db), user: User = Depends(AdminOnly)):
    try:
        affected = reject_report_queue_jobs(db, payload.job_ids, user=user, reason=payload.reason)
    except report_queue_scheduler.ReportQueueSchedulerError as exc:
        raise _queue_action_error(exc) from exc
    return ReportQueueActionResponse(affected_job_ids=affected, message=f"已拒绝 {len(affected)} 个任务")
