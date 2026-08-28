"""Administrator-only global report settings endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.schemas.system_setting import ReportContactSettingsRead, ReportContactSettingsUpdate
from app.service.system_setting_service import load_report_contact_settings, update_report_contact_settings
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
